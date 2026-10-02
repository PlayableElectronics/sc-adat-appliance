#define _POSIX_C_SOURCE 200809L
#include <jack/jack.h>
#include <jack/ringbuffer.h>
#include <sndfile.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/statvfs.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

/* Independent JACK capture. The RT callback only copies complete fixed-size
 * frames into a bounded ring; all filesystem and libsndfile work is non-RT. */
#define INPUTS 19
#define RATE 48000
#define RING_BYTES (8u * 1024u * 1024u)
#define DEFAULT_RESERVE_BYTES (5ull * 1024ull * 1024ull * 1024ull)
typedef struct { char name[96]; int channels, first; SNDFILE *file; SF_INFO info; } Track;
static jack_port_t *ports[INPUTS];
static jack_ringbuffer_t *ring;
static float interleaved[4096 * INPUTS];
static atomic_int running = 1;
static atomic_int stop_reason = 0; /* 1 clean stop, 2 full, 3 I/O/ring failure, 4 mount lost */
static atomic_ullong dropped_frames = 0, callbacks = 0, xrun_count = 0;
static Track tracks[INPUTS]; static int track_count;
static char session[1024]; static unsigned segment_seconds = 900; static uint64_t reserve_bytes=DEFAULT_RESERVE_BYTES;

static void report_status(const char *state,size_t frames,unsigned segments) {
    char path[1200],temp[1240]; snprintf(path,sizeof path,"%s/recorder.status",session); snprintf(temp,sizeof temp,"%s.tmp",path);
    FILE *f=fopen(temp,"w"); if(!f)return;
    fprintf(f,"state=%s\ndropped_frames=%llu\nframes_written=%zu\nsegments=%u\nxrun_count=%llu\n",state,atomic_load(&dropped_frames),frames,segments,atomic_load(&xrun_count));
    if(fclose(f)==0) rename(temp,path); else unlink(temp);
}

static int process(jack_nframes_t nframes, void *unused) {
    (void)unused;
    if (!atomic_load_explicit(&running, memory_order_relaxed)) return 0;
    atomic_fetch_add_explicit(&callbacks, 1, memory_order_relaxed);
    const size_t frame_bytes = INPUTS * sizeof(float);
    if (nframes > 4096 || jack_ringbuffer_write_space(ring) < (size_t)nframes * frame_bytes) {
        atomic_fetch_add_explicit(&dropped_frames, nframes, memory_order_relaxed);
        atomic_store_explicit(&stop_reason,3,memory_order_relaxed);
        atomic_store_explicit(&running,0,memory_order_relaxed);
        return 0;
    }
    jack_default_audio_sample_t *in[INPUTS];
    for (int c=0; c<INPUTS; ++c) in[c] = jack_port_get_buffer(ports[c], nframes);
    for (jack_nframes_t i=0; i<nframes; ++i) {
        for (int c=0; c<INPUTS; ++c) interleaved[(size_t)i*INPUTS+c] = (float)in[c][i];
    }
    if(jack_ringbuffer_write(ring,(const char *)interleaved,(size_t)nframes*frame_bytes)!=(size_t)nframes*frame_bytes){
        atomic_fetch_add_explicit(&dropped_frames,nframes,memory_order_relaxed);
        atomic_store_explicit(&stop_reason,3,memory_order_relaxed); atomic_store_explicit(&running,0,memory_order_relaxed);
    }
    return 0;
}

static int load_plan(const char *path) {
    FILE *f=fopen(path,"r"); if (!f) return -1;
    char line[256]; int used[INPUTS]={0};
    while (fgets(line,sizeof line,f)) {
        if (line[0]=='#' || line[0]=='\n') continue;
        if(track_count>=INPUTS){fclose(f);return -1;}
        Track *t=&tracks[track_count];
        if (sscanf(line,"%95s %d %d",t->name,&t->channels,&t->first)!=3 ||
            t->channels<1 || t->channels>2 || t->first<0 || t->first+t->channels>INPUTS) { fclose(f); return -1; }
        for (int i=0;i<track_count;i++) if (!strcmp(tracks[i].name,t->name)) { fclose(f); return -1; }
        for(size_t c=0;c<strlen(t->name);c++) if(!( (t->name[c]>='a'&&t->name[c]<='z') || (t->name[c]>='A'&&t->name[c]<='Z') || (t->name[c]>='0'&&t->name[c]<='9') || t->name[c]=='_' || t->name[c]=='-' || t->name[c]=='.')){fclose(f);return -1;}
        for(int c=t->first;c<t->first+t->channels;c++){if(used[c]){fclose(f);return -1;}used[c]=1;}
        ++track_count;
    }
    fclose(f); for(int c=0;c<INPUTS;c++)if(!used[c])return -1; return track_count ? 0 : -1;
}

static int open_segment(unsigned index) {
    char dir[1200]; snprintf(dir,sizeof dir,"%s/segment-%03u",session,index);
    if (mkdir(dir,0750)) return -1;
    for (int i=0;i<track_count;i++) {
        char path[1400]; snprintf(path,sizeof path,"%s/%s.wav",dir,tracks[i].name);
        tracks[i].info=(SF_INFO){.samplerate=RATE,.channels=tracks[i].channels,.format=SF_FORMAT_WAV|SF_FORMAT_PCM_24};
        tracks[i].file=sf_open(path,SFM_WRITE,&tracks[i].info);
        if (!tracks[i].file) return -1;
    }
    return 0;
}

static int close_segment(void) {
    int failed=0;
    for (int i=0;i<track_count;i++) if (tracks[i].file) {
        if (sf_error(tracks[i].file)!=SF_ERR_NO_ERROR) failed=1;
        sf_write_sync(tracks[i].file);
        if (sf_close(tracks[i].file)!=SF_ERR_NO_ERROR) failed=1;
        tracks[i].file=NULL;
    }
    return failed;
}

static void *writer(void *unused) {
    (void)unused;
    const size_t frame_bytes=INPUTS*sizeof(float); float *block=malloc(4096*frame_bytes);
    if (!block || open_segment(0)) { (void)close_segment(); atomic_store(&stop_reason,3); atomic_store(&running,0); free(block); return NULL; }
    size_t used=0; unsigned segment=0; time_t opened=time(NULL),last_report=0; int final_segment=0;
    report_status("RECORDING",0,1);
    while (atomic_load(&running) || jack_ringbuffer_read_space(ring)>=frame_bytes) {
        size_t available=jack_ringbuffer_read_space(ring)/frame_bytes;
        if (!available) { usleep(2000); continue; }
        if (available>4096) available=4096;
        size_t got=jack_ringbuffer_read(ring,(char *)block,available*frame_bytes)/frame_bytes;
        for (int t=0;t<track_count;t++) {
            float out[4096*2];
            for(size_t f=0;f<got;f++) for(int c=0;c<tracks[t].channels;c++) out[f*tracks[t].channels+c]=block[f*INPUTS+tracks[t].first+c];
            if (!tracks[t].file || sf_writef_float(tracks[t].file,out,(sf_count_t)got)!=(sf_count_t)got) { atomic_store(&stop_reason,3); atomic_store(&running,0); }
        }
        used+=got;
        if(time(NULL)!=last_report){report_status(final_segment?"FINAL_SEGMENT":"RECORDING",used,segment+1);last_report=time(NULL);}
        struct statvfs fs;
        if (statvfs(session,&fs)) { atomic_store(&stop_reason,4); atomic_store(&running,0); break; }
        if ((uint64_t)fs.f_bavail*fs.f_frsize < reserve_bytes) { atomic_store(&stop_reason,2); atomic_store(&running,0); break; }
        if (!final_segment && time(NULL)-opened >= (time_t)segment_seconds) {
            if ((uint64_t)fs.f_bavail*fs.f_frsize < reserve_bytes+(uint64_t)segment_seconds*RATE*INPUTS*3) {
                report_status("FINAL_SEGMENT",used,segment+1);
                atomic_store(&stop_reason,2);
                atomic_store(&running,0);
                break;
            }
            if (close_segment()) { atomic_store(&stop_reason,3); atomic_store(&running,0); break; }
            ++segment; if (open_segment(segment)) { atomic_store(&stop_reason,3); atomic_store(&running,0); break; } opened=time(NULL);
        }
    }
    if (close_segment()) atomic_store(&stop_reason,3);
    int reason=atomic_load(&stop_reason); const char *state=reason==2?"STOPPED_FULL":reason==4?"DISK_LOST":reason==3||atomic_load(&dropped_frames)?"FAILED":"STOPPED";
    report_status(state,used,segment+1);
    free(block); return NULL;
}

static void stop(int sig) { (void)sig; atomic_store(&stop_reason,1); atomic_store(&running,0); }
static int xrun(void *unused) { (void)unused; atomic_fetch_add_explicit(&xrun_count,1,memory_order_relaxed); return 0; }
int main(int argc,char **argv) {
    if(argc!=5){fprintf(stderr,"usage: %s SESSION SEGMENT_SECONDS RESERVE_BYTES PLAN.tsv\n",argv[0]);return 2;}
    if(strlen(argv[1])>=sizeof session || load_plan(argv[4])){fprintf(stderr,"invalid session or track plan\n");return 2;}
    char *end=NULL; errno=0; unsigned long segment_value=strtoul(argv[2],&end,10);
    if(errno || end==argv[2] || *end || segment_value<1 || segment_value>7200)return 2;
    errno=0; end=NULL; unsigned long long reserve_value=strtoull(argv[3],&end,10);
    if(errno || end==argv[3] || *end || reserve_value==0)return 2;
    strcpy(session,argv[1]); segment_seconds=(unsigned)segment_value; reserve_bytes=(uint64_t)reserve_value;
    ring=jack_ringbuffer_create(RING_BYTES); if(!ring)return 2;
    jack_client_t *client=jack_client_open("sc-adat-recorder",JackNoStartServer,NULL); if(!client){fprintf(stderr,"JACK unavailable\n");return 3;}
    char name[32]; for(int i=0;i<INPUTS;i++){snprintf(name,sizeof name,"capture_%02d",i+1);ports[i]=jack_port_register(client,name,JACK_DEFAULT_AUDIO_TYPE,JackPortIsInput,0);if(!ports[i])return 3;}
    if(jack_set_process_callback(client,process,NULL) || jack_set_xrun_callback(client,xrun,NULL)){jack_client_close(client);return 3;}
    signal(SIGINT,stop);signal(SIGTERM,stop);
    if(jack_activate(client)){jack_client_close(client);return 3;}
    pthread_t thread; if(pthread_create(&thread,NULL,writer,NULL)){jack_deactivate(client);jack_client_close(client);return 3;}
    while(atomic_load(&running)) sleep(1);
    if(pthread_join(thread,NULL)){jack_deactivate(client);jack_client_close(client);jack_ringbuffer_free(ring);return 3;}
    jack_deactivate(client); jack_client_close(client); jack_ringbuffer_free(ring);
    return atomic_load(&dropped_frames)?4:0;
}

#define _POSIX_C_SOURCE 200809L
#include <jack/jack.h>
#include <jack/ringbuffer.h>
#include <sndfile.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/statvfs.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

/* JACK callback: copy complete frames into a bounded ring only. All WAV,
 * segment, metadata and filesystem operations run on the writer thread. */
#define INPUTS 19
#define SUPPORTED_RATE 48000
#define RING_BYTES (8u * 1024u * 1024u)
#define DEFAULT_RESERVE_BYTES (5ull * 1024ull * 1024ull * 1024ull)
#define MAX_CALLBACK_FRAMES 4096

typedef struct { char name[96]; int channels, first; } TrackPlan;
typedef struct { char directory[1200]; unsigned index; uint64_t start_frame, frame_count; SNDFILE *files[INPUTS]; SF_INFO info[INPUTS]; int open; } Segment;

static jack_port_t *ports[INPUTS];
static jack_ringbuffer_t *ring;
static float callback_frames[MAX_CALLBACK_FRAMES * INPUTS];
static TrackPlan plans[INPUTS];
static int track_count;
static Segment current_segment, next_segment, retired_segment;
static atomic_int running = 1;
static atomic_int stop_reason = 0; /* 1 clean, 2 full, 3 I/O/ring failure, 4 disk lost */
static atomic_int io_failure = 0;
static atomic_ullong dropped_frames = 0, callbacks = 0, xrun_count = 0;
static char session[1024];
static unsigned segment_seconds = 900, sample_rate = SUPPORTED_RATE;
static uint64_t reserve_bytes = DEFAULT_RESERVE_BYTES, segment_frame_limit;
static dev_t session_device;
typedef int (*free_space_probe_t)(const char *, uint64_t *);

static int filesystem_free_bytes(const char *path, uint64_t *free_bytes) {
    struct statvfs fs;
    if (statvfs(path, &fs)) return -1;
    *free_bytes = (uint64_t)fs.f_bavail * fs.f_frsize;
    return 0;
}

static free_space_probe_t free_space_probe = filesystem_free_bytes;

static int session_volume_present(void) {
    struct stat status;
    return stat(session, &status) == 0 && status.st_dev == session_device;
}

static int set_stop_reason(int wanted) {
    int expected = 0;
    return atomic_compare_exchange_strong(&stop_reason, &expected, wanted);
}

static void report_status(const char *state, uint64_t frames, unsigned segments) {
    if (!session_volume_present()) return;
    char path[1200], temp[1240];
    snprintf(path, sizeof path, "%s/recorder.status", session);
    snprintf(temp, sizeof temp, "%s.tmp", path);
    FILE *file = fopen(temp, "w");
    if (!file) return;
    fprintf(file, "state=%s\ndropped_frames=%llu\nframes_written=%llu\nsegments=%u\nxrun_count=%llu\n",
            state, atomic_load(&dropped_frames), (unsigned long long)frames, segments,
            atomic_load(&xrun_count));
    if (fclose(file) == 0) (void)rename(temp, path); else (void)unlink(temp);
}

static int process(jack_nframes_t nframes, void *unused) {
    (void)unused;
    if (!atomic_load_explicit(&running, memory_order_relaxed)) return 0;
    atomic_fetch_add_explicit(&callbacks, 1, memory_order_relaxed);
    const size_t frame_bytes = INPUTS * sizeof(float);
    if (nframes > MAX_CALLBACK_FRAMES || jack_ringbuffer_write_space(ring) < (size_t)nframes * frame_bytes) {
        atomic_fetch_add_explicit(&dropped_frames, nframes, memory_order_relaxed);
        (void)set_stop_reason(3);
        atomic_store_explicit(&running, 0, memory_order_relaxed);
        return 0;
    }
    jack_default_audio_sample_t *input[INPUTS];
    for (int c = 0; c < INPUTS; ++c) input[c] = jack_port_get_buffer(ports[c], nframes);
    for (jack_nframes_t frame = 0; frame < nframes; ++frame)
        for (int channel = 0; channel < INPUTS; ++channel)
            callback_frames[(size_t)frame * INPUTS + channel] = (float)input[channel][frame];
    const size_t bytes = (size_t)nframes * frame_bytes;
    if (jack_ringbuffer_write(ring, (const char *)callback_frames, bytes) != bytes) {
        atomic_fetch_add_explicit(&dropped_frames, nframes, memory_order_relaxed);
        (void)set_stop_reason(3);
        atomic_store_explicit(&running, 0, memory_order_relaxed);
    }
    return 0;
}

static int load_plan(const char *path) {
    FILE *file = fopen(path, "r");
    if (!file) return -1;
    char line[256]; int used[INPUTS] = {0};
    while (fgets(line, sizeof line, file)) {
        if (line[0] == '#' || line[0] == '\n') continue;
        if (track_count >= INPUTS) { fclose(file); return -1; }
        TrackPlan *plan = &plans[track_count];
        if (sscanf(line, "%95s %d %d", plan->name, &plan->channels, &plan->first) != 3 ||
            plan->channels < 1 || plan->channels > 2 || plan->first < 0 || plan->first + plan->channels > INPUTS) { fclose(file); return -1; }
        for (int i = 0; i < track_count; ++i) if (!strcmp(plans[i].name, plan->name)) { fclose(file); return -1; }
        for (size_t c = 0; c < strlen(plan->name); ++c) {
            char ch = plan->name[c];
            if (!((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '_' || ch == '-' || ch == '.')) { fclose(file); return -1; }
        }
        for (int c = plan->first; c < plan->first + plan->channels; ++c) { if (used[c]) { fclose(file); return -1; } used[c] = 1; }
        ++track_count;
    }
    fclose(file);
    for (int c = 0; c < INPUTS; ++c) if (!used[c]) return -1;
    return track_count ? 0 : -1;
}

static void segment_paths(unsigned index, char *final_path, size_t final_size, char *work_path, size_t work_size, int staging) {
    snprintf(final_path, final_size, "%s/segment-%03u", session, index);
    if (staging) snprintf(work_path, work_size, "%s/.segment-%03u.next", session, index);
    else snprintf(work_path, work_size, "%s", final_path);
}

static int segment_open(Segment *segment, unsigned index, uint64_t start_frame, int staging) {
    char final_path[1200], work_path[1200];
    segment_paths(index, final_path, sizeof final_path, work_path, sizeof work_path, staging);
    if (!session_volume_present() || mkdir(work_path, 0750)) { atomic_store(&io_failure, 1); return -1; }
    memset(segment, 0, sizeof *segment);
    segment->index = index; segment->start_frame = start_frame;
    snprintf(segment->directory, sizeof segment->directory, "%s", work_path);
    for (int i = 0; i < track_count; ++i) {
        char path[1400];
        snprintf(path, sizeof path, "%s/%s.wav", work_path, plans[i].name);
        segment->info[i] = (SF_INFO){.samplerate=(int)sample_rate, .channels=plans[i].channels, .format=SF_FORMAT_WAV|SF_FORMAT_PCM_24};
        segment->files[i] = sf_open(path, SFM_WRITE, &segment->info[i]);
        if (!segment->files[i]) {
            atomic_store(&io_failure, 1);
            for (int opened = 0; opened <= i; ++opened) if (segment->files[opened]) {
                sf_close(segment->files[opened]); segment->files[opened] = NULL;
            }
            for (int track = 0; track <= i; ++track) {
                char partial[1400]; snprintf(partial, sizeof partial, "%s/%s.wav", work_path, plans[track].name); (void)unlink(partial);
            }
            (void)rmdir(work_path);
            return -1;
        }
    }
    segment->open = 1;
    return 0;
}

static int segment_finish(Segment *segment, int finalized) {
    if (!segment->open) return 0;
    int failed = 0;
    for (int i = 0; i < track_count; ++i) {
        if (!segment->files[i]) { failed = 1; continue; }
        if (sf_error(segment->files[i]) != SF_ERR_NO_ERROR) failed = 1;
        sf_write_sync(segment->files[i]);
        if (sf_error(segment->files[i]) != SF_ERR_NO_ERROR) failed = 1;
        if (sf_close(segment->files[i]) != SF_ERR_NO_ERROR) failed = 1;
        segment->files[i] = NULL;
    }
    char path[1400]; snprintf(path, sizeof path, "%s/segment.json", segment->directory);
    FILE *metadata = session_volume_present() ? fopen(path, "w") : NULL;
    if (!metadata) failed = 1;
    else {
        fprintf(metadata, "{\n  \"segment_index\": %u,\n  \"start_frame\": %llu,\n  \"frame_count\": %llu,\n  \"sample_rate\": %u,\n  \"finalized\": %s\n}\n",
                segment->index, (unsigned long long)segment->start_frame,
                (unsigned long long)segment->frame_count, sample_rate, finalized && !failed ? "true" : "false");
        if (fclose(metadata)) failed = 1;
    }
    segment->open = 0;
    if (failed) atomic_store(&io_failure, 1);
    return failed ? -1 : 0;
}

static int segment_write(Segment *segment, const float *frames, size_t count) {
    float output[MAX_CALLBACK_FRAMES * 2];
    if (!segment->open || count > MAX_CALLBACK_FRAMES) return -1;
    for (int track = 0; track < track_count; ++track) {
        if (!segment->files[track]) { atomic_store(&io_failure, 1); return -1; }
        for (size_t f = 0; f < count; ++f)
            for (int c = 0; c < plans[track].channels; ++c)
                output[f * (size_t)plans[track].channels + c] = frames[f * INPUTS + plans[track].first + c];
        if (sf_writef_float(segment->files[track], output, (sf_count_t)count) != (sf_count_t)count) {
            atomic_store(&io_failure, 1); return -1;
        }
    }
    segment->frame_count += count;
    return 0;
}

static int promote_next_segment(void) {
    if (!session_volume_present()) { (void)set_stop_reason(4); return -1; }
    uint64_t free_bytes;
    uint64_t next_bytes = segment_frame_limit * INPUTS * 3;
    if (free_space_probe(session, &free_bytes)) { (void)set_stop_reason(4); return -1; }
    if (free_bytes < reserve_bytes || free_bytes - reserve_bytes < next_bytes) {
        (void)set_stop_reason(2);
        return 0;
    }
    if (!next_segment.open) return 0;
    if (retired_segment.open && segment_finish(&retired_segment, 1)) return -1;
    char final_path[1200], unused[1200];
    segment_paths(next_segment.index, final_path, sizeof final_path, unused, sizeof unused, 0);
    if (rename(next_segment.directory, final_path)) { atomic_store(&io_failure, 1); return -1; }
    snprintf(next_segment.directory, sizeof next_segment.directory, "%s", final_path);
    retired_segment = current_segment;
    current_segment = next_segment;
    memset(&next_segment, 0, sizeof next_segment);
    return 1;
}

static int prepare_next_segment(int check_space) {
    if (next_segment.open) return 0;
    if (check_space) {
        struct statvfs fs;
        uint64_t next_bytes = segment_frame_limit * INPUTS * 3;
        if (!session_volume_present() || statvfs(session, &fs)) { (void)set_stop_reason(4); return -1; }
        if ((uint64_t)fs.f_bavail * fs.f_frsize < reserve_bytes + next_bytes) return 1;
    }
    if (segment_open(&next_segment, current_segment.index + 1,
                     current_segment.start_frame + segment_frame_limit, 1)) return -1;
    return 0;
}

static int writer_begin(const char *session_path, unsigned rate, uint64_t frames_per_segment, int test_mode) {
    if (strlen(session_path) >= sizeof session || !rate || !frames_per_segment) return -1;
    if (session_path != session) strcpy(session, session_path);
    sample_rate = rate; segment_frame_limit = frames_per_segment;
    struct stat session_stat;
    if (stat(session, &session_stat)) return -1;
    session_device = session_stat.st_dev;
    if (segment_open(&current_segment, 0, 0, 0)) return -1;
    return prepare_next_segment(!test_mode);
}

/* Shared by the live writer and deterministic fixture. A block crossing a
 * boundary is split at the exact frame; no JACK stop/restart is involved. */
static int writer_append(const float *frames, size_t count, size_t *consumed, int test_mode) {
    size_t offset = 0;
    while (offset < count) {
        if (current_segment.frame_count == segment_frame_limit) {
            int promoted = promote_next_segment();
            if (promoted < 0) { *consumed = offset; return -1; }
            if (!promoted) { (void)set_stop_reason(2); *consumed = offset; return 1; }
        }
        uint64_t remaining = segment_frame_limit - current_segment.frame_count;
        size_t take = count - offset;
        if ((uint64_t)take > remaining) take = (size_t)remaining;
        if (segment_write(&current_segment, frames + offset * INPUTS, take)) { *consumed = offset; return -1; }
        offset += take;
        if (current_segment.frame_count == segment_frame_limit && !next_segment.open) {
            (void)set_stop_reason(2);
            *consumed = offset; return 1;
        }
    }
    if (retired_segment.open && segment_finish(&retired_segment, 1)) { *consumed = offset; return -1; }
    if (!next_segment.open && current_segment.frame_count < segment_frame_limit) {
        int prepared = prepare_next_segment(!test_mode);
        if (prepared < 0) { *consumed = offset; return -1; }
    }
    *consumed = offset;
    return 0;
}

static int writer_finish(int finalized) {
    int failed = 0;
    if (next_segment.open) {
        /* An unused pre-opened segment contains no captured frames; discard it. */
        for (int i = 0; i < track_count; ++i) if (next_segment.files[i]) {
            if (sf_close(next_segment.files[i]) != SF_ERR_NO_ERROR) atomic_store(&io_failure, 1);
            next_segment.files[i] = NULL;
        }
        for (int i = 0; i < track_count; ++i) {
            char path[1400]; snprintf(path, sizeof path, "%s/%s.wav", next_segment.directory, plans[i].name); (void)unlink(path);
        }
        (void)rmdir(next_segment.directory); memset(&next_segment, 0, sizeof next_segment);
    }
    if (retired_segment.open && segment_finish(&retired_segment, 1)) failed = 1;
    if (segment_finish(&current_segment, finalized)) failed = 1;
    if (failed) atomic_store(&io_failure, 1);
    return failed ? -1 : 0;
}

static void *writer(void *unused) {
    (void)unused;
    const size_t frame_bytes = INPUTS * sizeof(float);
    float *block = malloc(MAX_CALLBACK_FRAMES * frame_bytes);
    if (!block || writer_begin(session, sample_rate, (uint64_t)segment_seconds * sample_rate, 0) < 0) {
        atomic_store(&io_failure, 1); (void)set_stop_reason(3); atomic_store(&running, 0); free(block); return NULL;
    }
    report_status("RECORDING", 0, 1);
    uint64_t written = 0; time_t last_report = 0;
    while (atomic_load(&running) || jack_ringbuffer_read_space(ring) >= frame_bytes) {
        size_t available = jack_ringbuffer_read_space(ring) / frame_bytes;
        if (!available) {
            struct timespec wait = {.tv_sec = 0, .tv_nsec = 2000000};
            nanosleep(&wait, NULL);
            continue;
        }
        if (available > MAX_CALLBACK_FRAMES) available = MAX_CALLBACK_FRAMES;
        size_t got = jack_ringbuffer_read(ring, (char *)block, available * frame_bytes) / frame_bytes;
        if (!got) continue;
        size_t consumed = 0;
        int result = writer_append(block, got, &consumed, 0);
        written += consumed;
        if (result < 0) { (void)set_stop_reason(3); atomic_store(&running, 0); }
        if (result > 0) atomic_store(&running, 0);
        if (time(NULL) != last_report) {
            unsigned segments = current_segment.index + 1;
            report_status(atomic_load(&stop_reason) == 2 ? "FINAL_SEGMENT" : "RECORDING", written, segments);
            last_report = time(NULL);
        }
        struct statvfs fs;
        if (atomic_load(&running) && (!session_volume_present() || statvfs(session, &fs))) {
            (void)set_stop_reason(4); atomic_store(&running, 0);
        } else if (atomic_load(&running) && (uint64_t)fs.f_bavail * fs.f_frsize < reserve_bytes) {
            (void)set_stop_reason(2); atomic_store(&running, 0);
        }
    }
    int reason = atomic_load(&stop_reason);
    (void)writer_finish(reason == 0 || reason == 1 || reason == 2);
    reason = atomic_load(&stop_reason);
    const char *state = reason == 2 ? "STOPPED_FULL" : reason == 4 ? "DISK_LOST" :
                        reason == 3 || atomic_load(&io_failure) || atomic_load(&dropped_frames) ? "FAILED" : "STOPPED";
    report_status(state, written, current_segment.index + 1);
    free(block);
    return NULL;
}

static void stop(int sig) { (void)sig; (void)set_stop_reason(1); atomic_store(&running, 0); }
static void disk_lost_stop(int sig) { (void)sig; atomic_store(&stop_reason, 4); atomic_store(&running, 0); }
static int xrun(void *unused) { (void)unused; atomic_fetch_add_explicit(&xrun_count, 1, memory_order_relaxed); return 0; }
static int recorder_exit_status(void) { return atomic_load(&dropped_frames) || atomic_load(&io_failure) ? 4 : 0; }

#ifndef SC_ADAT_RECORDER_NO_MAIN
int main(int argc, char **argv) {
    if (argc != 5) { fprintf(stderr, "usage: %s SESSION SEGMENT_SECONDS RESERVE_BYTES PLAN.tsv\n", argv[0]); return 2; }
    if (strlen(argv[1]) >= sizeof session || load_plan(argv[4])) { fprintf(stderr, "invalid session or track plan\n"); return 2; }
    char *end = NULL; errno = 0; unsigned long segment_value = strtoul(argv[2], &end, 10);
    if (errno || end == argv[2] || *end || segment_value < 1 || segment_value > 7200) return 2;
    errno = 0; end = NULL; unsigned long long reserve_value = strtoull(argv[3], &end, 10);
    if (errno || end == argv[3] || *end || reserve_value == 0) return 2;
    strcpy(session, argv[1]); segment_seconds = (unsigned)segment_value; reserve_bytes = (uint64_t)reserve_value;
    ring = jack_ringbuffer_create(RING_BYTES); if (!ring) return 2;
    jack_client_t *client = jack_client_open("sc-adat-recorder", JackNoStartServer, NULL);
    if (!client) { fprintf(stderr, "JACK unavailable\n"); return 3; }
    sample_rate = jack_get_sample_rate(client);
    if (sample_rate != SUPPORTED_RATE) { fprintf(stderr, "unsupported JACK rate %u; required %u Hz\n", sample_rate, SUPPORTED_RATE); jack_client_close(client); return 3; }
    char name[32];
    for (int i = 0; i < INPUTS; ++i) { snprintf(name, sizeof name, "capture_%02d", i + 1); ports[i] = jack_port_register(client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0); if (!ports[i]) { jack_client_close(client); return 3; } }
    if (jack_set_process_callback(client, process, NULL) || jack_set_xrun_callback(client, xrun, NULL)) { jack_client_close(client); return 3; }
    signal(SIGINT, stop); signal(SIGTERM, stop); signal(SIGUSR1, disk_lost_stop);
    if (jack_activate(client)) { jack_client_close(client); return 3; }
    pthread_t thread;
    if (pthread_create(&thread, NULL, writer, NULL)) { jack_deactivate(client); jack_client_close(client); return 3; }
    while (atomic_load(&running)) sleep(1);
    if (pthread_join(thread, NULL)) { jack_deactivate(client); jack_client_close(client); jack_ringbuffer_free(ring); return 3; }
    jack_deactivate(client); jack_client_close(client); jack_ringbuffer_free(ring);
    return recorder_exit_status();
}
#endif

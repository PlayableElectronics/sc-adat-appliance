#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <unistd.h>

static unsigned char *p; static size_t left;
static void put32(uint32_t v) { if (left < 4) exit(2); p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;p+=4;left-=4; }
static void str(const char *s) { size_t n=strlen(s), z=(n+4)&~3; if(left<z)exit(2); memcpy(p,s,n); memset(p+n,0,z-n);p+=z;left-=z; }
static void i32(int32_t v) { put32((uint32_t)v); }
static void f32(float f) { uint32_t v; memcpy(&v,&f,4); put32(v); }
static int open_reply(struct sockaddr_in *a) {
  int fd=socket(AF_INET,SOCK_DGRAM,0); struct sockaddr_in local; if(fd<0)return -1;
  memset(&local,0,sizeof(local)); local.sin_family=AF_INET; local.sin_addr.s_addr=htonl(INADDR_LOOPBACK); local.sin_port=0;
  if(bind(fd,(struct sockaddr*)&local,sizeof(local))<0){close(fd);return -1;}
  const char *port=getenv("SC_ADAT_OSC_PORT");
  memset(a,0,sizeof(*a)); a->sin_family=AF_INET; a->sin_port=htons((uint16_t)(port ? atoi(port) : 57110)); a->sin_addr.s_addr=htonl(INADDR_LOOPBACK);
  return fd;
}
static int packet(const char *addr,const char *types,int argc,const char **args) {
  unsigned char b[4096]; p=b;left=sizeof(b); str(addr); str(types);
  int ai=0; for(const char *t=types+1;*t;t++,ai++) { if(*t=='i')i32(atoi(args[ai])); else if(*t=='f')f32((float)atof(args[ai])); else if(*t=='s')str(args[ai]); }
  struct sockaddr_in a; int fd=open_reply(&a); if(fd<0)return 1;
  int r=sendto(fd,b,(size_t)(p-b),0,(struct sockaddr*)&a,sizeof(a))==(ssize_t)(p-b)?0:1; close(fd); return r;
}
static int wait_node(int fd, struct sockaddr_in *a, unsigned char *b, size_t n, int32_t wanted) {
  if(sendto(fd,b,n,0,(struct sockaddr*)a,sizeof(*a))!=(ssize_t)n)return 1;
  for(int tries=0;tries<4;tries++){
    fd_set set; struct timeval tv={1,0}; unsigned char reply[4096]; ssize_t got;
    FD_ZERO(&set); FD_SET(fd,&set); int ready=select(fd+1,&set,NULL,NULL,&tv);
    if(ready<0 && errno==EINTR){tries--;continue;} if(ready<=0)continue;
    got=recv(fd,reply,sizeof(reply),0); if(got<4)continue;
    size_t na=strnlen((char*)reply,(size_t)got); if(na==(size_t)got)continue; size_t pos=(na+4)&~3;
    if(pos+4>(size_t)got)continue;
    if(!strcmp((char*)reply,"/fail"))return 1;
    if(strcmp((char*)reply,"/n_go"))continue;
    size_t nt=strnlen((char*)reply+pos,(size_t)got-pos); pos+=(nt+4)&~3;
    if(pos+4>(size_t)got)continue; uint32_t wire; memcpy(&wire,reply+pos,4);
    if((int32_t)ntohl(wire)==wanted)return 0;
  }
  return 2;
}
static int create_node(const char *types, int argc, const char **args, int32_t node) {
  unsigned char b[4096]; struct sockaddr_in a; int fd=open_reply(&a); if(fd<0)return 1;
  p=b; left=sizeof(b); str("/notify"); str(",i"); i32(1);
  if(sendto(fd,b,(size_t)(p-b),0,(struct sockaddr*)&a,sizeof(a))!=(ssize_t)(p-b)){close(fd);return 1;}
  p=b; left=sizeof(b); str("/s_new"); str(types);
  int ai=0; for(const char *t=types+1;*t;t++,ai++){if(*t=='i')i32(atoi(args[ai]));else if(*t=='f')f32((float)atof(args[ai]));else if(*t=='s')str(args[ai]);}
  int rc=wait_node(fd,&a,b,(size_t)(p-b),node); close(fd); return rc;
}
int main(int argc,char **argv) {
  if(argc<2)return 2;
  if(!strcmp(argv[1],"free")) { const char *a[]={argv[2]}; return packet("/n_free",",i",1,a); }
  if(!strcmp(argv[1],"start") && argc >= 3) { const char *a[]={"sc_adat_tone24","1000",getenv("SC_ADAT_TONE_ACTION")?getenv("SC_ADAT_TONE_ACTION"):"0",getenv("SC_ADAT_TONE_TARGET")?getenv("SC_ADAT_TONE_TARGET"):"0","level",argv[2],"gate","1"}; return create_node(",siiisfsf",8,a,1000); }
  if(!strcmp(argv[1],"scan") && argc >= 5) { const char *a[]={"sc_adat_scan","2000",getenv("SC_ADAT_TONE_ACTION")?getenv("SC_ADAT_TONE_ACTION"):"0",getenv("SC_ADAT_TONE_TARGET")?getenv("SC_ADAT_TONE_TARGET"):"0","output",argv[2],"freq",argv[3],"level",argv[4],"gate","1"}; return create_node(",siiisisfsfsf",12,a,2000); }
  if(!strcmp(argv[1],"release") && argc >= 3) { const char *a[]={argv[2],"gate","0"}; return packet("/n_set",",isf",3,a); }
  if(!strcmp(argv[1],"set") && argc >= 5) { const char *a[]={argv[2],argv[3],argv[4]}; return packet("/n_set",",isf",3,a); }
  return 2;
}

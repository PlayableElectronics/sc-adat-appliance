#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static unsigned char *cursor; static size_t remaining;
static void put32(uint32_t v) { if (remaining < 4) exit(2); *cursor++=v>>24; *cursor++=v>>16; *cursor++=v>>8; *cursor++=v; remaining-=4; }
static void oscstr(const char *s) { size_t n=strlen(s), z=(n+4)&~3; if (remaining<z) exit(2); memcpy(cursor,s,n); memset(cursor+n,0,z-n); cursor+=z; remaining-=z; }
static void oscint(int32_t v) { put32((uint32_t)v); }
static void blob(const unsigned char *data, size_t n) { put32((uint32_t)n); if (remaining<n) exit(2); memcpy(cursor,data,n); cursor+=n; remaining-=n; while (n++&3) { if (!remaining) exit(2); *cursor++=0; remaining--; } }
static size_t packet(unsigned char *buf, size_t cap, const char *address, const char *types) { cursor=buf; remaining=cap; oscstr(address); oscstr(types); return (size_t)(cursor-buf); }
static int open_reply(struct sockaddr_in *target) {
  int fd=socket(AF_INET,SOCK_DGRAM,0); struct sockaddr_in local;
  if (fd<0) return -1; memset(&local,0,sizeof local); local.sin_family=AF_INET; local.sin_addr.s_addr=htonl(INADDR_LOOPBACK); local.sin_port=0;
  if (bind(fd,(struct sockaddr *)&local,sizeof local)<0) { close(fd); return -1; }
  memset(target,0,sizeof *target); target->sin_family=AF_INET; target->sin_addr.s_addr=htonl(INADDR_LOOPBACK); target->sin_port=htons((uint16_t)(getenv("SC_ADAT_OSC_PORT") ? atoi(getenv("SC_ADAT_OSC_PORT")) : 57110)); return fd;
}
static int send_wait(int fd, struct sockaddr_in *target, unsigned char *msg, size_t n, const char *want, int32_t cookie, int check_cookie) {
  if (sendto(fd,msg,n,0,(struct sockaddr *)target,sizeof *target)!=(ssize_t)n) return 1;
  for (int tries=0; tries<4; tries++) {
    fd_set set; struct timeval tv={1,0}; unsigned char reply[4096]; ssize_t got; FD_ZERO(&set); FD_SET(fd,&set);
    int ready=select(fd+1,&set,NULL,NULL,&tv); if (ready<0 && errno==EINTR) continue; if (ready<=0) continue;
    got=recv(fd,reply,sizeof reply,0); if (got<4) continue;
    size_t naddr=strnlen((char *)reply,(size_t)got); if (naddr==(size_t)got) continue; size_t pos=(naddr+4)&~3;
    if (pos+4>(size_t)got || strcmp((char *)reply,want)!=0) { if (strncmp((char *)reply,"/fail",5)==0) return 1; continue; }
    if (!check_cookie) return 0;
    if (pos+4>(size_t)got) return 1; size_t nt=strnlen((char *)reply+pos,(size_t)got-pos); pos+=(nt+4)&~3;
    uint32_t wire; if (pos+4>(size_t)got) return 1; memcpy(&wire,reply+pos,4);
    if ((int32_t)ntohl(wire)!=cookie) return 1; return 0;
  }
  return 2;
}
static int send_only(int fd, struct sockaddr_in *target, unsigned char *msg, size_t n) {
  return sendto(fd,msg,n,0,(struct sockaddr *)target,sizeof *target)==(ssize_t)n ? 0 : 1;
}
static int load_one(int fd, struct sockaddr_in *target, const char *path) {
  FILE *f=fopen(path,"rb"); unsigned char data[131072], msg[140000]; size_t n, pos;
  if (!f) return 1; n=fread(data,1,sizeof data,f); int bad=ferror(f); fclose(f); if (!n || bad) return 1;
  packet(msg,sizeof msg,"/d_recv",",b"); blob(data,n); return send_wait(fd,target,msg,(size_t)(cursor-msg),"/done",0,0);
}
static int send_sync(int fd, struct sockaddr_in *target) {
  unsigned char msg[64]; int32_t cookie=(int32_t)getpid(); packet(msg,sizeof msg,"/sync",",i"); oscint(cookie); return send_wait(fd,target,msg,(size_t)(cursor-msg),"/synced",cookie,1);
}
int main(int argc, char **argv) {
  struct sockaddr_in target; int fd, rc=0;
  if (argc<2) return 2; fd=open_reply(&target); if (fd<0) return 1;
  if (!strcmp(argv[1],"load")) { if (argc<3) rc=2; else for (int i=2; i<argc && !rc; i++) rc=load_one(fd,&target,argv[i]); if (!rc) puts("/done"); }
  else if (!strcmp(argv[1],"sync")) { rc=send_sync(fd,&target); if (!rc) puts("/synced"); }
  else if (!strcmp(argv[1],"validate")) {
    unsigned char msg[256]; const char *args[]={"sc_adat_tone24","19000","0","0","level","-120","gate","1"};
    packet(msg,sizeof msg,"/s_new",",siiisfsi");
    for (int i=0; i<8; i++) { char t=",siiisfsi"[i+1]; if(t=='s') oscstr(args[i]); else if(t=='i') oscint(atoi(args[i])); else { uint32_t bits; float v=(float)atof(args[i]); memcpy(&bits,&v,4); put32(bits); } }
    size_t n=(size_t)(cursor-msg); rc=send_only(fd,&target,msg,n); if (!rc) rc=send_sync(fd,&target); if (!rc) { packet(msg,sizeof msg,"/n_free",",i"); oscint(19000); n=(size_t)(cursor-msg); rc=send_only(fd,&target,msg,n); } if (!rc) puts("VALID");
  }
  else if (!strcmp(argv[1],"activate")) { rc=send_sync(fd,&target); if (!rc) puts("ACTIVATED"); }
  else rc=2;
  close(fd); return rc;
}

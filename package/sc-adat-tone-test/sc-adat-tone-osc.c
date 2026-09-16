#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static unsigned char *p; static size_t left;
static void put32(uint32_t v) { if (left < 4) exit(2); p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;p+=4;left-=4; }
static void str(const char *s) { size_t n=strlen(s), z=(n+4)&~3; if(left<z)exit(2); memcpy(p,s,n); memset(p+n,0,z-n);p+=z;left-=z; }
static void i32(int32_t v) { put32((uint32_t)v); }
static void f32(float f) { uint32_t v; memcpy(&v,&f,4); put32(v); }
static int send_packet(const unsigned char *b,size_t n) {
  int fd=socket(AF_INET,SOCK_DGRAM,0); struct sockaddr_in a; if(fd<0)return 1;
  const char *port=getenv("SC_ADAT_OSC_PORT");
  memset(&a,0,sizeof(a)); a.sin_family=AF_INET; a.sin_port=htons((uint16_t)(port ? atoi(port) : 57110)); a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
  int r=sendto(fd,b,n,0,(struct sockaddr*)&a,sizeof(a)); close(fd); return r==(int)n?0:1;
}
static int packet(const char *addr,const char *types,int argc,const char **args) {
  unsigned char b[4096]; p=b;left=sizeof(b); str(addr); str(types);
  int ai=0; for(const char *t=types+1;*t;t++,ai++) { if(*t=='i')i32(atoi(args[ai])); else if(*t=='f')f32((float)atof(args[ai])); else if(*t=='s')str(args[ai]); }
  return send_packet(b,(size_t)(p-b));
}
int main(int argc,char **argv) {
  if(argc<2)return 2;
  if(!strcmp(argv[1],"free")) { const char *a[]={argv[2]}; return packet("/n_free",",i",1,a); }
  if(!strcmp(argv[1],"start") && argc >= 3) { const char *a[]={"sc_adat_tone24","1000","0","0","level",argv[2],"gate","1"}; return packet("/s_new",",siiisfsf",8,a); }
  if(!strcmp(argv[1],"scan") && argc >= 5) { const char *a[]={"sc_adat_scan","2000","0","0","output",argv[2],"freq",argv[3],"level",argv[4],"gate","1"}; return packet("/s_new",",siiisisfsfsf",12,a); }
  if(!strcmp(argv[1],"release") && argc >= 3) { const char *a[]={argv[2],"gate","0"}; return packet("/n_set",",isf",3,a); }
  if(!strcmp(argv[1],"set") && argc >= 5) { const char *a[]={argv[2],argv[3],argv[4]}; return packet("/n_set",",isf",3,a); }
  return 2;
}

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned char *b; static size_t n, p;
static int strv(const char *want) {
  size_t s=p, z;
  while (p<n && b[p]) p++;
  if (p>=n) return 1;
  z=(p-s+4)&~3;
  if (p-s != strlen((char *)b+s) || p+1>n || s+z>n) return 1;
  while (p<s+z) if (b[p++]) return 1;
  return strcmp((char *)b+s,want)!=0;
}
static int i32(int32_t want) {
  if (p+4>n) return 1;
  uint32_t v=(uint32_t)b[p]<<24|(uint32_t)b[p+1]<<16|(uint32_t)b[p+2]<<8|b[p+3]; p+=4;
  return (int32_t)v!=want;
}
static int f32(float want) {
  if (p+4>n) return 1;
  uint32_t v=(uint32_t)b[p]<<24|(uint32_t)b[p+1]<<16|(uint32_t)b[p+2]<<8|b[p+3], w;
  memcpy(&w,&want,4); p+=4; return v!=w;
}
int main(int argc,char **argv) {
  FILE *f; if (argc!=2) return 2; f=fopen(argv[1],"rb"); if(!f)return 2;
  fseek(f,0,SEEK_END); n=(size_t)ftell(f); rewind(f); b=malloc(n);
  if(!b || fread(b,1,n,f)!=n)return 2; fclose(f);
  if(strv("/s_new") || strv(",siiisfsf") || strv("sc_adat_tone24") ||
     i32(19000) || i32(0) || i32(0) || strv("level") || f32(-120.0f) ||
     strv("gate") || f32(1.0f) || p!=n) return 1;
  puts("PASS OSC packet fields, floats and padding"); return 0;
}

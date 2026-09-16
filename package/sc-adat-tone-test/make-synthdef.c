#include <stdio.h>
#include <stdint.h>
#include <string.h>
static FILE *f; static void u32(uint32_t v){fputc(v>>24,f);fputc(v>>16,f);fputc(v>>8,f);fputc(v,f);} static void fl(float x){uint32_t v;memcpy(&v,&x,4);u32(v);} static void s(const char*x){size_t n=strlen(x);fputc(n,f);fwrite(x,1,n,f);while((n+1)%4)fputc(0,f),n++;}
int main(int c,char**v){int i;if(c!=2)return 2;f=fopen(v[1],"wb");if(!f)return 1;fwrite("SCgf",1,4,f);u32(2);u32(1);s("sc_adat_tone24");u32(2);fl(0);fl(1);u32(2);s("level");s("gate");u32(48);
for(i=0;i<24;i++){s("SinOsc");u32(2);u32(2);u32(1);u32(0);u32((uint32_t)-1);fl(200+i*50);u32((uint32_t)-1);fl(0);fputc(2,f);} for(i=0;i<24;i++){s("Out");u32(2);u32(2);u32(0);u32(0);u32((uint32_t)-1);fl((float)i);u32(2+i);fl(0); }u32(0);fclose(f);return 0;}

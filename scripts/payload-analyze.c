#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static uint32_t u32(unsigned char *p) { return p[0]|p[1]<<8|p[2]<<16|p[3]<<24; }
static uint16_t u16(unsigned char *p) { return p[0]|p[1]<<8; }
int main(int ac,char **av) { FILE *f; unsigned char h[44],ch[8]; float *x; size_t n,frames; long data=0; double mean[26]={0},rms[26]={0}; int scan, crossings[26]={0};
 if(ac!=3||(f=fopen(av[2],"rb"))==0)return 2; scan=!strcmp(av[1],"scan"); if(!scan&&!strcmp(av[1],"tone")){} else if(!scan)return 2; if(fread(h,1,12,f)!=12||memcmp(h,"RIFF",4)||memcmp(h+8,"WAVE",4)){fclose(f);return 3;} while(fread(ch,1,8,f)==8) { uint32_t size=u32(ch+4); if(!memcmp(ch,"fmt ",4)) { unsigned char fmt[32]={0}; if(size<16||size>sizeof fmt||fread(fmt,1,size,f)!=size||u16(fmt+2)!=26||u16(fmt+14)!=32)return 3; } else if(!memcmp(ch,"data",4)) { data=ftell(f); n=size/4; break; } else fseek(f,size+(size&1),SEEK_CUR); } if(!data||fseek(f,data,SEEK_SET)){fclose(f);return 3;} x=malloc(n*sizeof *x); if(!x||fread(x,4,n,f)!=n){fclose(f);free(x);return 3;} fclose(f); frames=n/26;
 for(size_t i=0;i<n;i++) { int c=i%26; mean[c]+=x[i]; rms[c]+=x[i]*x[i]; }
 for(int c=0;c<26;c++) { mean[c]/=frames; rms[c]=sqrt(rms[c]/frames); if((scan ? c==7 : c<24) && (rms[c]<0.005 || fabs(mean[c])>0.001)) return 4; if((scan ? c!=7 : c>=24) && rms[c]>0.00001) return 5; for(size_t i=26*20000+c;i<26*70000 && i<n;i+=26) if((x[i-26]<0)!=(x[i]<0)) crossings[c]++; if((scan ? c==7 : c<24) && (fabs((double)crossings[c]*48000.0/100000.0-(scan?550:200+50*c))>8)) return 6; }
 printf("NRT %s channels=26 frames=%zu active=%s silent=25,26 rms_ch1=%.6f dc_ch1=%.6f\n",scan?"scan":"tone",frames,scan?"7":"1-24",rms[0],mean[0]); free(x); return 0; }

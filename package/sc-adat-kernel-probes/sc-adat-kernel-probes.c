#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ipc.h>
#include <sys/sem.h>
#include <sys/socket.h>
#include <net/ethernet.h>
#include <arpa/inet.h>
#include <string.h>
#include <unistd.h>

int main(void)
{
    int failures = 0;
    int fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));

    if (fd < 0) {
        printf("AF_PACKET socket: FAIL (%s)\n", strerror(errno));
        failures++;
    } else {
        printf("AF_PACKET socket: PASS\n");
        close(fd);
    }

    int semid = semget(IPC_PRIVATE, 1, IPC_CREAT | 0600);
    if (semid < 0) {
        printf("SysV semaphore creation: FAIL (%s)\n", strerror(errno));
        failures++;
    } else {
        printf("SysV semaphore creation: PASS\n");
        if (semctl(semid, 0, IPC_RMID) < 0) {
            printf("SysV semaphore removal: FAIL (%s)\n", strerror(errno));
            failures++;
        }
    }

    return failures ? EXIT_FAILURE : EXIT_SUCCESS;
}

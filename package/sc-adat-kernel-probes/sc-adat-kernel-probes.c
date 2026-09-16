#define _XOPEN_SOURCE 600
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/ipc.h>
#include <sys/sem.h>
#include <sys/socket.h>
#include <net/ethernet.h>
#include <arpa/inet.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>

static int pty_probe(void)
{
    int master, slave;
    char *name;

    master = posix_openpt(O_RDWR | O_NOCTTY);
    if (master < 0) {
        printf("PTY allocation: FAIL (%s)\n", strerror(errno));
        return EXIT_FAILURE;
    }
    if (grantpt(master) < 0 || unlockpt(master) < 0) {
        printf("PTY setup: FAIL (%s)\n", strerror(errno));
        close(master);
        return EXIT_FAILURE;
    }
    name = ptsname(master);
    if (name == NULL || (slave = open(name, O_RDWR | O_NOCTTY)) < 0) {
        printf("PTY slave: FAIL (%s)\n", strerror(errno));
        close(master);
        return EXIT_FAILURE;
    }
    close(slave);
    close(master);
    printf("PTY allocation: PASS\n");
    return EXIT_SUCCESS;
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--pty") == 0)
        return pty_probe();

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

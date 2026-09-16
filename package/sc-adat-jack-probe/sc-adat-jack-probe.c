#include <jack/jack.h>
#include <stdio.h>

int main(void) {
    jack_status_t status = 0;
    jack_client_t *client = jack_client_open("sc-adat-probe", JackNoStartServer, &status);
    if (!client) return 1;
    printf("rate=%u\nperiod=%u\n", jack_get_sample_rate(client), jack_get_buffer_size(client));
    const char **ports = jack_get_ports(client, NULL, JACK_DEFAULT_AUDIO_TYPE, 0);
    if (ports) {
        for (size_t i = 0; ports[i]; ++i) {
            jack_port_t *port = jack_port_by_name(client, ports[i]);
            unsigned flags = port ? jack_port_flags(port) : 0;
            if (flags & JackPortIsPhysical) {
                if (flags & JackPortIsOutput) printf("PHYSICAL_CAPTURE %s\n", ports[i]);
                if (flags & JackPortIsInput) printf("PHYSICAL_PLAYBACK %s\n", ports[i]);
            }
            printf("PORT %s\n", ports[i]);
        }
        jack_free(ports);
    }
    jack_client_close(client);
    return 0;
}

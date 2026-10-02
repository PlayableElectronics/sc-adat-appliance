#define SC_ADAT_RECORDER_NO_MAIN
#include "../../package/sc-adat-recorder/sc-adat-recorder.c"

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    for (int i = 0; i < INPUTS; ++i) {
        snprintf(plans[i].name, sizeof plans[i].name, "channel_%02d", i + 1);
        plans[i].channels = 1; plans[i].first = i;
    }
    track_count = INPUTS;
    const uint64_t total_frames = 37, frames_per_segment = 10;
    strcpy(session, argv[1]);
    if (mkdir(session, 0750) || writer_begin(session, SUPPORTED_RATE, frames_per_segment, 1) < 0) return 3;
    char reference_dir[1200]; snprintf(reference_dir, sizeof reference_dir, "%s/reference", argv[2]);
    if (mkdir(reference_dir, 0750)) return 4;
    SNDFILE *reference[INPUTS] = {0}; SF_INFO info[INPUTS];
    for (int channel = 0; channel < INPUTS; ++channel) {
        char path[1400]; snprintf(path, sizeof path, "%s/channel_%02d.wav", reference_dir, channel + 1);
        info[channel] = (SF_INFO){.samplerate=SUPPORTED_RATE,.channels=1,.format=SF_FORMAT_WAV|SF_FORMAT_PCM_24};
        reference[channel] = sf_open(path, SFM_WRITE, &info[channel]);
        if (!reference[channel]) return 5;
    }
    const size_t blocks[] = {7, 6, 11, 13};
    float block[13 * INPUTS]; uint64_t frame = 0;
    for (size_t block_index = 0; block_index < sizeof blocks / sizeof blocks[0]; ++block_index) {
        size_t count = blocks[block_index];
        for (size_t f = 0; f < count; ++f)
            for (int channel = 0; channel < INPUTS; ++channel)
                block[f * INPUTS + channel] = (float)((int)(((frame + f) * INPUTS + (uint64_t)channel) % 71) - 35) / 64.0f;
        for (int channel = 0; channel < INPUTS; ++channel) {
            float mono[13];
            for (size_t f = 0; f < count; ++f) mono[f] = block[f * INPUTS + (size_t)channel];
            if (sf_writef_float(reference[channel], mono, (sf_count_t)count) != (sf_count_t)count) return 6;
        }
        size_t consumed = 0;
        int result = writer_append(block, count, &consumed, 1);
        if (result != 0 || consumed != count) return 7;
        frame += count;
    }
    if (frame != total_frames || writer_finish(1)) return 8;
    for (int channel = 0; channel < INPUTS; ++channel)
        if (sf_close(reference[channel]) != SF_ERR_NO_ERROR) return 9;
    char failure_root[1200], occupied[1400];
    snprintf(failure_root, sizeof failure_root, "%s/open-failure", argv[2]);
    snprintf(occupied, sizeof occupied, "%s/segment-000", failure_root);
    if (mkdir(failure_root, 0750) || mkdir(occupied, 0750)) return 10;
    strcpy(session, failure_root);
    struct stat failure_stat;
    if (stat(session, &failure_stat)) return 11;
    session_device = failure_stat.st_dev;
    atomic_store(&io_failure, 0);
    if (segment_open(&current_segment, 0, 0, 0) == 0 || !atomic_load(&io_failure) || atomic_load(&dropped_frames) != 0 || recorder_exit_status() == 0) return 12;

    char write_root[1200], close_root[1200];
    snprintf(write_root, sizeof write_root, "%s/write-failure", argv[2]);
    snprintf(close_root, sizeof close_root, "%s/close-failure", argv[2]);
    if (mkdir(write_root, 0750) || mkdir(close_root, 0750)) return 13;

    strcpy(session, write_root); if (stat(session, &failure_stat)) return 14;
    session_device = failure_stat.st_dev; atomic_store(&io_failure, 0); atomic_store(&dropped_frames, 0);
    if (writer_begin(session, SUPPORTED_RATE, 10, 1) < 0) return 15;
    if (sf_close(current_segment.files[0]) != SF_ERR_NO_ERROR) return 16;
    current_segment.files[0] = NULL;
    float one_frame[INPUTS] = {0}; size_t consumed = 0;
    if (writer_append(one_frame, 1, &consumed, 1) == 0 || atomic_load(&dropped_frames) != 0 || recorder_exit_status() == 0) return 17;
    (void)writer_finish(0);

    strcpy(session, close_root); if (stat(session, &failure_stat)) return 18;
    session_device = failure_stat.st_dev; atomic_store(&io_failure, 0); atomic_store(&dropped_frames, 0);
    if (writer_begin(session, SUPPORTED_RATE, 10, 1) < 0) return 19;
    if (sf_close(current_segment.files[0]) != SF_ERR_NO_ERROR) return 20;
    current_segment.files[0] = NULL;
    if (segment_finish(&current_segment, 1) == 0 || atomic_load(&dropped_frames) != 0 || recorder_exit_status() == 0) return 21;
    return 0;
}

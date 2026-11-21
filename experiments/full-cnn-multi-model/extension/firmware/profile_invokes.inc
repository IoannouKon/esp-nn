// Included inside app_main after the original warm-up loop.
struct InvocationMeasurement {
    int64_t us;
    uint32_t cycles;
    MeanMeasurement mean;
};
const auto invoke = [&](bool enable_profile) {
    profile_mean = enable_profile;
    mean_measurement = {};
    std::memcpy(in->data.int8, input_start, in->bytes);
    const uint32_t cycle_start = esp_cpu_get_cycle_count();
    const int64_t start = esp_timer_get_time();
    const auto status = interpreter.Invoke();
    const int64_t elapsed = esp_timer_get_time() - start;
    const uint32_t cycles = esp_cpu_get_cycle_count() - cycle_start;
    check(status == kTfLiteOk, "profile invoke");
    return InvocationMeasurement{elapsed, cycles, mean_measurement};
};

std::vector<InvocationMeasurement> plain(CNN_SAMPLES), instrumented(CNN_SAMPLES);
std::vector<MeanMeasurement> calibration(CNN_SAMPLES);
std::vector<int64_t> times;
std::vector<uint32_t> cycles;
std::vector<uint8_t> reference(out->bytes);
bool equal_outputs = true;
uint32_t checksum = 2166136261u;
for (int i = 0; i < CNN_SAMPLES; ++i) {
    // Alternate which sample in each pair invokes the nested MEAN timer first.
    for (int j = 0; j < 2; ++j) {
        const bool enabled = (i + j) % 2 != 0;
        auto& result = enabled ? instrumented[i] : plain[i];
        result = invoke(enabled);
        check(result.mean.calls == unsigned(enabled), "MEAN profile call count");
        if (i == 0 && j == 0) std::memcpy(reference.data(), out->data.int8, out->bytes);
        else if (std::memcmp(reference.data(), out->data.int8, out->bytes)) equal_outputs = false;
        vTaskDelay(1);
    }
    times.push_back(plain[i].us);
    cycles.push_back(plain[i].cycles);
}
profile_mean = false;
for (auto& entry : calibration) {
    const MeanTimer timer;
    asm volatile("" ::: "memory");
    entry = timer.Read();
}
for (int i = 0; i < CNN_SAMPLES; ++i) {
    std::printf("CNN_RUN index=%d us=%" PRId64 " cycles=%" PRIu32 "\n",
                i, plain[i].us, plain[i].cycles);
    const auto& measured = instrumented[i];
    std::printf("CNN_PROFILE index=%d us=%" PRId64 " cycles=%" PRIu32
                " mean_us=%" PRId64 " mean_cycles=%" PRIu32 " calls=%" PRIu32 "\n",
                i, measured.us, measured.cycles, measured.mean.us, measured.mean.cycles, measured.mean.calls);
    std::printf("CNN_EMPTY index=%d us=%" PRId64 " cycles=%" PRIu32 "\n",
                i, calibration[i].us, calibration[i].cycles);
}

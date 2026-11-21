extern const uint8_t cases_start[] asm("_binary_correctness_inputs_bin_start");
extern const uint8_t cases_end[] asm("_binary_correctness_inputs_bin_end");
const size_t length = cases_end - cases_start;
check(in->bytes > 0 && length % in->bytes == 0 && length / in->bytes >= 10, "extra inputs");
std::vector<int8_t> guarded_input(in->bytes + 64, 0x53);
for (size_t i = 0; i < length / in->bytes; ++i) {
    const uint8_t* data = cases_start + i * in->bytes;
    // Preserve a guarded host-input copy as well as the read-only flash fixture.
    std::memcpy(guarded_input.data() + 32, data, in->bytes);
    std::memcpy(in->data.int8, guarded_input.data() + 32, in->bytes);
    std::printf("CNN_CASE index=%u\n", unsigned(i));
    ProbeReset();
    check(interpreter.Invoke() == kTfLiteOk, "extra correctness invoke");
    ProbeReport();
    std::printf("CNN_CASE_OUTPUT index=%u bytes=%u hex=", unsigned(i), unsigned(out->bytes));
    for (size_t byte = 0; byte < out->bytes; ++byte) {
        std::printf("%02x", static_cast<unsigned>(static_cast<uint8_t>(out->data.int8[byte])));
    }
    std::puts("");
    check(std::memcmp(guarded_input.data() + 32, data, in->bytes) == 0 &&
          std::all_of(guarded_input.begin(), guarded_input.begin() + 32, [](int8_t b) { return b == 0x53; }) &&
          std::all_of(guarded_input.end() - 32, guarded_input.end(), [](int8_t b) { return b == 0x53; }),
          "extra input guard");
    check(heap_caps_check_integrity_all(true), "heap integrity after correctness invoke");
    vTaskDelay(1);
}
std::printf("CNN_CASE_DONE cases=%u heap_integrity=ok arena_guard=ok stack_high_water_bytes=%u\n",
            unsigned(length / in->bytes), unsigned(uxTaskGetStackHighWaterMark(nullptr)));

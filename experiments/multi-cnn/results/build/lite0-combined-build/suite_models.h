extern const uint8_t model_0_start[] asm("_binary_model_0_tflite_start");
extern const uint8_t model_0_end[] asm("_binary_model_0_tflite_end");
extern const uint8_t input_0_start[] asm("_binary_input_0_bin_start");
extern const uint8_t input_0_end[] asm("_binary_input_0_bin_end");

constexpr ModelBlob kModels[] = {
    {"efficientnet_lite0", model_0_start, model_0_end, input_0_start, input_0_end, nullptr, nullptr},
};

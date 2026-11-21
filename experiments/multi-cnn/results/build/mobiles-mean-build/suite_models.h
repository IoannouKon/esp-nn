extern const uint8_t model_0_start[] asm("_binary_model_0_tflite_start");
extern const uint8_t model_0_end[] asm("_binary_model_0_tflite_end");
extern const uint8_t input_0_start[] asm("_binary_input_0_bin_start");
extern const uint8_t input_0_end[] asm("_binary_input_0_bin_end");
extern const uint8_t model_1_start[] asm("_binary_model_1_tflite_start");
extern const uint8_t model_1_end[] asm("_binary_model_1_tflite_end");
extern const uint8_t input_1_start[] asm("_binary_input_1_bin_start");
extern const uint8_t input_1_end[] asm("_binary_input_1_bin_end");

constexpr ModelBlob kModels[] = {
    {"mobilenet_v2", model_0_start, model_0_end, input_0_start, input_0_end, nullptr, nullptr},
    {"mobilenet_v3_small", model_1_start, model_1_end, input_1_start, input_1_end, nullptr, nullptr},
};

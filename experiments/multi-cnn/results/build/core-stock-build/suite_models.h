extern const uint8_t model_0_start[] asm("_binary_model_0_tflite_start");
extern const uint8_t model_0_end[] asm("_binary_model_0_tflite_end");
extern const uint8_t input_0_start[] asm("_binary_input_0_bin_start");
extern const uint8_t input_0_end[] asm("_binary_input_0_bin_end");
extern const uint8_t validation_0_start[] asm("_binary_validation_0_bin_start");
extern const uint8_t validation_0_end[] asm("_binary_validation_0_bin_end");
extern const uint8_t model_1_start[] asm("_binary_model_1_tflite_start");
extern const uint8_t model_1_end[] asm("_binary_model_1_tflite_end");
extern const uint8_t input_1_start[] asm("_binary_input_1_bin_start");
extern const uint8_t input_1_end[] asm("_binary_input_1_bin_end");
extern const uint8_t validation_1_start[] asm("_binary_validation_1_bin_start");
extern const uint8_t validation_1_end[] asm("_binary_validation_1_bin_end");
extern const uint8_t model_2_start[] asm("_binary_model_2_tflite_start");
extern const uint8_t model_2_end[] asm("_binary_model_2_tflite_end");
extern const uint8_t input_2_start[] asm("_binary_input_2_bin_start");
extern const uint8_t input_2_end[] asm("_binary_input_2_bin_end");
extern const uint8_t validation_2_start[] asm("_binary_validation_2_bin_start");
extern const uint8_t validation_2_end[] asm("_binary_validation_2_bin_end");
extern const uint8_t model_3_start[] asm("_binary_model_3_tflite_start");
extern const uint8_t model_3_end[] asm("_binary_model_3_tflite_end");
extern const uint8_t input_3_start[] asm("_binary_input_3_bin_start");
extern const uint8_t input_3_end[] asm("_binary_input_3_bin_end");
extern const uint8_t validation_3_start[] asm("_binary_validation_3_bin_start");
extern const uint8_t validation_3_end[] asm("_binary_validation_3_bin_end");
extern const uint8_t model_4_start[] asm("_binary_model_4_tflite_start");
extern const uint8_t model_4_end[] asm("_binary_model_4_tflite_end");
extern const uint8_t input_4_start[] asm("_binary_input_4_bin_start");
extern const uint8_t input_4_end[] asm("_binary_input_4_bin_end");
extern const uint8_t validation_4_start[] asm("_binary_validation_4_bin_start");
extern const uint8_t validation_4_end[] asm("_binary_validation_4_bin_end");
extern const uint8_t model_5_start[] asm("_binary_model_5_tflite_start");
extern const uint8_t model_5_end[] asm("_binary_model_5_tflite_end");
extern const uint8_t input_5_start[] asm("_binary_input_5_bin_start");
extern const uint8_t input_5_end[] asm("_binary_input_5_bin_end");
extern const uint8_t validation_5_start[] asm("_binary_validation_5_bin_start");
extern const uint8_t validation_5_end[] asm("_binary_validation_5_bin_end");
extern const uint8_t model_6_start[] asm("_binary_model_6_tflite_start");
extern const uint8_t model_6_end[] asm("_binary_model_6_tflite_end");
extern const uint8_t input_6_start[] asm("_binary_input_6_bin_start");
extern const uint8_t input_6_end[] asm("_binary_input_6_bin_end");
extern const uint8_t validation_6_start[] asm("_binary_validation_6_bin_start");
extern const uint8_t validation_6_end[] asm("_binary_validation_6_bin_end");
extern const uint8_t model_7_start[] asm("_binary_model_7_tflite_start");
extern const uint8_t model_7_end[] asm("_binary_model_7_tflite_end");
extern const uint8_t input_7_start[] asm("_binary_input_7_bin_start");
extern const uint8_t input_7_end[] asm("_binary_input_7_bin_end");
extern const uint8_t validation_7_start[] asm("_binary_validation_7_bin_start");
extern const uint8_t validation_7_end[] asm("_binary_validation_7_bin_end");
extern const uint8_t model_8_start[] asm("_binary_model_8_tflite_start");
extern const uint8_t model_8_end[] asm("_binary_model_8_tflite_end");
extern const uint8_t input_8_start[] asm("_binary_input_8_bin_start");
extern const uint8_t input_8_end[] asm("_binary_input_8_bin_end");

constexpr ModelBlob kModels[] = {
    {"mnist_fixed", model_0_start, model_0_end, input_0_start, input_0_end, validation_0_start, validation_0_end},
    {"max3", model_1_start, model_1_end, input_1_start, input_1_end, validation_1_start, validation_1_end},
    {"max5", model_2_start, model_2_end, input_2_start, input_2_end, validation_2_start, validation_2_end},
    {"mean_only", model_3_start, model_3_end, input_3_start, input_3_end, validation_3_start, validation_3_end},
    {"both", model_4_start, model_4_end, input_4_start, input_4_end, validation_4_start, validation_4_end},
    {"depthwise_both", model_5_start, model_5_end, input_5_start, input_5_end, validation_5_start, validation_5_end},
    {"avg_control", model_6_start, model_6_end, input_6_start, input_6_end, validation_6_start, validation_6_end},
    {"neutral_control", model_7_start, model_7_end, input_7_start, input_7_end, validation_7_start, validation_7_end},
    {"person_detection", model_8_start, model_8_end, input_8_start, input_8_end, nullptr, nullptr},
};

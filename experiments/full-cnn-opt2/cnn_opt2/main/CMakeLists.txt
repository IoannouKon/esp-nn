set(sources main.cc)
if(PROBE_OPT2)
    list(APPEND sources probe.cc)
endif()

idf_component_register(
    SRCS ${sources}
    PRIV_REQUIRES esp_timer heap esp_psram esp_hw_support
    EMBED_FILES model.tflite input.bin
)

if(PROBE_OPT2)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE PROBE_OPT2=1)
    target_link_options(${COMPONENT_LIB} INTERFACE
        "LINKER:-u,__wrap_esp_nn_max_pool_s8_esp32s3"
        "LINKER:--wrap=esp_nn_max_pool_s8_esp32s3"
        "LINKER:--wrap=esp_nn_max_pool_s8_esp32s3_sliding_row_asm")
endif()

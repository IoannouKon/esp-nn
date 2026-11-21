set(sources main.cc)
if(CNN_DISPATCH_PROBE)
    list(APPEND sources probe.cc)
endif()
idf_component_register(
    SRCS ${sources}
    PRIV_REQUIRES esp_timer heap esp_psram esp_hw_support
    EMBED_FILES "model.tflite" "input.bin"
)
if(DEFINED CNN_ARENA_BYTES)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE CNN_ARENA_BYTES=${CNN_ARENA_BYTES})
endif()
if(CNN_WATCHDOG_MS)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE CNN_WATCHDOG_MS=${CNN_WATCHDOG_MS})
endif()
if(CNN_DISPATCH_PROBE)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE CNN_DISPATCH_PROBE=1)
    target_link_options(${COMPONENT_LIB} INTERFACE
        "LINKER:--wrap=esp_nn_max_pool_s8_esp32s3"
        "LINKER:--wrap=esp_nn_max_pool_s8_esp32s3_sliding_row_asm"
        "LINKER:--wrap=esp_nn_mean_s8_16ch_qacc")
endif()

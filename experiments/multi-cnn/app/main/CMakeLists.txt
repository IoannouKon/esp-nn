include("${CMAKE_CURRENT_LIST_DIR}/suite_models.cmake")
set(app_sources main.cc mean_bridge.cc)
if(CNN_DIAGNOSTIC)
    list(APPEND app_sources probe.cc)
endif()
idf_component_register(
    SRCS ${app_sources}
    PRIV_REQUIRES esp_timer heap esp_psram esp_hw_support espressif__esp-nn
    EMBED_FILES ${model_files}
)
if(DEFINED CNN_ARENA_BYTES)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE CNN_ARENA_BYTES=${CNN_ARENA_BYTES})
endif()
if(CNN_DIAGNOSTIC)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE CNN_DIAGNOSTIC=1)
    target_link_options(${COMPONENT_LIB} INTERFACE
        "LINKER:--wrap=esp_nn_max_pool_s8_esp32s3"
        "LINKER:--wrap=esp_nn_max_pool_s8_esp32s3_sliding_row_asm"
        "LINKER:--wrap=esp_nn_mean_s8_16ch_qacc")
endif()

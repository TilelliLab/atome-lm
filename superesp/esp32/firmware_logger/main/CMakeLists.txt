# SuperESP data-logger firmware component (no model — just sensors -> CSV serial).
idf_component_register(
    SRCS "${CMAKE_CURRENT_LIST_DIR}/logger_main.c"
    INCLUDE_DIRS "${CMAKE_CURRENT_LIST_DIR}"
    REQUIRES esp_adc driver
)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -Wno-unused-function)

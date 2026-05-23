# CMakeLists.txt — Atome LLM generation firmware for the Raspberry Pi Pico (RP2040).
#
# Build prerequisite: the Pico SDK (https://github.com/raspberrypi/pico-sdk).
#   export PICO_SDK_PATH=/path/to/pico-sdk
#
# Build:
#   mkdir build && cd build
#   cmake .. && make -j
#
# Output: atome_pico.uf2 — drag-drop onto the RPI-RP2 mass-storage device,
# then open a serial terminal at 115200 8N1 to read generated tokens.
cmake_minimum_required(VERSION 3.13)

include(${CMAKE_CURRENT_LIST_DIR}/pico_sdk_import.cmake)

project(atome_pico C CXX ASM)
set(CMAKE_C_STANDARD 99)

pico_sdk_init()

set(ATOME_UPSTREAM ${CMAKE_CURRENT_LIST_DIR}/../../upstream)

add_executable(atome_pico
    main.c
    ${ATOME_UPSTREAM}/atome.c
)

target_include_directories(atome_pico PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}
    ${ATOME_UPSTREAM}
)

# Default config — small enough that the .atome blob fits comfortably
# in the RP2040's 2 MB flash. Override via `cmake -DATOME_D_MODEL=...`.
target_compile_definitions(atome_pico PRIVATE
    ATOME_D_MODEL=64
    ATOME_MAX_SEQ=32
    ATOME_N_LAYERS=4
    ATOME_N_PATHWAYS=3
    ATOME_VOCAB_SIZE=256
    ATOME_D_HEAD=16
    ATOME_KERNEL_SIZE=5
    ATOME_TOP_K=4
    DEMO_PROMPT_LEN=4
    DEMO_NEW_TOKENS=16
)

target_link_libraries(atome_pico
    pico_stdlib
    hardware_timer
)

# Route printf to USB CDC (no UART wiring required) AND UART (for boards
# without USB exposed). Both stay enabled at runtime; the Pico SDK fans
# the writes out to whichever hosts subscribe.
pico_enable_stdio_usb(atome_pico  1)
pico_enable_stdio_uart(atome_pico 1)

pico_add_extra_outputs(atome_pico)  # produces .uf2 + .bin + .map

# SuperESP battery component. Reuses the single-source battery_main.c (the one
# QEMU validated) + the vendored Atome engine + the generated battery_data.h.
# Config MUST match superesp/framework/config.py SHARED (d=32, L=2, ...).
set(SE   "${CMAKE_CURRENT_LIST_DIR}/../..")          # superesp/esp32
set(ROOT "${SE}/../..")                              # repo root

idf_component_register(
    SRCS "${SE}/battery_main.c" "${ROOT}/c_engine/upstream/atome.c"
    INCLUDE_DIRS "${SE}" "${ROOT}/c_engine/upstream"
    REQUIRES esp_timer        # esp_timer_get_time; esp_system/heap are always-available
)

set(_defs ATOME_D_MODEL=32 ATOME_N_LAYERS=2 ATOME_D_HEAD=8
          ATOME_MAX_SEQ=32  ATOME_TOP_K=4   ATOME_KERNEL_SIZE=5
          ATOME_VOCAB_SIZE=256 ATOME_MAX_CLASSES=16 ATOME_N_PATHWAYS=3)
target_compile_definitions(${COMPONENT_LIB} PRIVATE ${_defs})
target_compile_options(${COMPONENT_LIB} PRIVATE -O3 -ffast-math -funroll-loops -Wno-unused-function)

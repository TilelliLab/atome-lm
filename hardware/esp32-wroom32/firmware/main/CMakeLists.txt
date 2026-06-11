# Atome firmware component.
#
# ATOME_TOY (cache var, default OFF):
#   OFF -> 944K model (coherent output, needs PSRAM): d=256 L=8 head=64
#   ON  -> 20KB toy model (fits no-PSRAM boards, degenerate output): d=64 L=4 head=16
# Pass with:  idf.py -D ATOME_TOY=ON build

# The embedded symbol name is derived from the filename, so we ALWAYS embed a
# file literally named "model.atome" (symbol _binary_model_atome_start, used by
# main.c). atome.sh copies the chosen checkpoint into model.atome before build.
#
# ATOME_PROFILE selects the compile-time architecture (must match the blob):
#   full  (default) 944K, seq=128  -> needs PSRAM (~811KB state)   [model_full.atome]
#   wroom           944K, seq=32   -> internal SRAM (~209KB state) [model_full.atome]
#   toy             20KB, seq=64    -> fits anything, gibberish     [model_toy.atome]
if(NOT DEFINED ATOME_PROFILE)
    if(ATOME_TOY)            # back-compat with -D ATOME_TOY=ON
        set(ATOME_PROFILE "toy")
    else()
        set(ATOME_PROFILE "full")
    endif()
endif()

if(ATOME_PROFILE STREQUAL "toy")
    set(_defs ATOME_D_MODEL=64  ATOME_N_LAYERS=4 ATOME_D_HEAD=16
              ATOME_MAX_SEQ=64   ATOME_TOP_K=4    ATOME_KERNEL_SIZE=5)
elseif(ATOME_PROFILE STREQUAL "wroom")
    # seq=24 -> ~159KB state, fits classic-ESP32's ~168KB largest contiguous block
    # (measured on a real WROOM-32: 369KB free but biggest single block only 168KB).
    set(_defs ATOME_D_MODEL=256 ATOME_N_LAYERS=8 ATOME_D_HEAD=64
              ATOME_MAX_SEQ=24   ATOME_TOP_K=4    ATOME_KERNEL_SIZE=5)
else()  # full
    set(_defs ATOME_D_MODEL=256 ATOME_N_LAYERS=8 ATOME_D_HEAD=64
              ATOME_MAX_SEQ=128  ATOME_TOP_K=4    ATOME_KERNEL_SIZE=5)
endif()
message(STATUS "Atome build profile: ${ATOME_PROFILE}")

idf_component_register(
    SRCS "main.c" "atome.c"
    INCLUDE_DIRS "."
    EMBED_FILES "model.atome"
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE ${_defs})

# Engine uses fast-math-friendly float kernels; keep it warning-clean but lean.
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -ffast-math -Wno-unused-function)

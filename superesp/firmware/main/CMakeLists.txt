# SuperESP firmware component (ESP-IDF). Build-only skeleton.
#
# Compile-time config MUST match superesp/framework/config.py SHARED:
#   d_model=32 n_layers=2 d_head=8 top_k=4 kernel=5 vocab=256 max_seq=32 max_classes=16
# The OS head blob is embedded; copy superesp/artifacts/os_telem.atomecl here
# as os_telem.atomecl before building (symbol _binary_os_telem_atomecl_start).

idf_component_register(
    SRCS "superesp_main.c" "atome.c"
    INCLUDE_DIRS "."
    EMBED_FILES "os_telem.atomecl"
)

set(_defs ATOME_D_MODEL=32 ATOME_N_LAYERS=2 ATOME_D_HEAD=8
          ATOME_MAX_SEQ=32  ATOME_TOP_K=4   ATOME_KERNEL_SIZE=5
          ATOME_VOCAB_SIZE=256 ATOME_MAX_CLASSES=16 ATOME_N_PATHWAYS=3)

target_compile_definitions(${COMPONENT_LIB} PRIVATE ${_defs})
# -O3 enables the optimized branchless 4-trits/byte ternary kernel best
# (~2-3x faster classify/generate, measured on host; on-silicon NOT MEASURED).
target_compile_options(${COMPONENT_LIB} PRIVATE -O3 -ffast-math -funroll-loops -Wno-unused-function)

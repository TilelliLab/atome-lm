/*
 * libc_stubs.c — the handful of libc symbols atome.c needs
 * (memcpy/memset/memcmp from <string.h>, errno for libm's sqrtf/expf
 * domain-error paths), written by hand instead of linking newlib's
 * -lc.
 *
 * Measured in Faza 0: linking the real -lc pulls in newlib's
 * reentrancy struct, stdio FILE table and malloc arena (_impure_data,
 * __sf, __malloc_av_, ...) even though none of it is used. That alone
 * overflowed the 16 KB data RAM budget by 1252 bytes. These ~15 lines
 * replace it; -lm and -lgcc are still linked normally for sqrtf/expf/
 * tanhf and the softfloat add/sub/mul/div/compare routines.
 */
#include <stddef.h>

void *memcpy(void *dst, const void *src, size_t n) {
    unsigned char *d = dst;
    const unsigned char *s = src;
    while (n--) *d++ = *s++;
    return dst;
}

void *memset(void *dst, int c, size_t n) {
    unsigned char *d = dst;
    while (n--) *d++ = (unsigned char)c;
    return dst;
}

int memcmp(const void *a, const void *b, size_t n) {
    const unsigned char *pa = a, *pb = b;
    while (n--) {
        if (*pa != *pb) return *pa - *pb;
        pa++; pb++;
    }
    return 0;
}

int errno;
int *__errno(void) { return &errno; }

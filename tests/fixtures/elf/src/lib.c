#include <string.h>

int copy_first(const char *s) {
    char buf[64];
    strcpy(buf, s);
    return buf[0];
}

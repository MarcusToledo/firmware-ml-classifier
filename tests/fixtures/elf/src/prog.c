#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    char buf[64];
    strcpy(buf, argc > 1 ? argv[1] : "x");
    puts(buf);
    return 0;
}

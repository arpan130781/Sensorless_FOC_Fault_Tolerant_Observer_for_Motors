#include <stdio.h>
#include <assert.h>
#include <math.h>

void test_clarke_park() {
    float a = 1.0f, b = -0.5f, c = -0.5f;
    float alpha = (2.0f/3.0f) * (a - 0.5f * b - 0.5f * c);
    float beta = (2.0f/3.0f) * ((sqrtf(3.0f)/2.0f) * b - (sqrtf(3.0f)/2.0f) * c);
    
    assert(fabsf(alpha - 1.0f) < 1e-4);
    assert(fabsf(beta - 0.0f) < 1e-4);
    
    float theta = M_PI / 4.0f;
    float d = alpha * cosf(theta) + beta * sinf(theta);
    float q = -alpha * sinf(theta) + beta * cosf(theta);
    
    assert(fabsf(d - cosf(theta)) < 1e-4);
    assert(fabsf(q + sinf(theta)) < 1e-4);
    
    printf("Clarke/Park tests passed.\n");
}

int main() {
    test_clarke_park();
    return 0;
}

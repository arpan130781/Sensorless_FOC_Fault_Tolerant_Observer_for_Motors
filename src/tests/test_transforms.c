#include <stdio.h>
#include <assert.h>
#include <math.h>
#include "../foc_api.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

void test_clarke_known_vectors(void) {
    float alpha = 0.0f, beta = 0.0f;

    // Vector along A-axis: a=1.0, b=-0.5, c=-0.5 -> alpha=1.0, beta=0.0
    clarke_transform(1.0f, -0.5f, -0.5f, &alpha, &beta);
    assert(fabsf(alpha - 1.0f) < 1e-5f);
    assert(fabsf(beta - 0.0f) < 1e-5f);

    // Vector along B-C axis: a=0.0, b=sqrt(3)/2, c=-sqrt(3)/2 -> alpha=0.0, beta=1.0
    float sqrt3_2 = sqrtf(3.0f) / 2.0f;
    clarke_transform(0.0f, sqrt3_2, -sqrt3_2, &alpha, &beta);
    assert(fabsf(alpha - 0.0f) < 1e-5f);
    assert(fabsf(beta - 1.0f) < 1e-5f);
}

void test_inv_clarke_known_vectors(void) {
    float a = 0.0f, b = 0.0f, c = 0.0f;

    // alpha=1.0, beta=0.0 -> a=1.0, b=-0.5, c=-0.5
    inv_clarke_transform(1.0f, 0.0f, &a, &b, &c);
    assert(fabsf(a - 1.0f) < 1e-5f);
    assert(fabsf(b - (-0.5f)) < 1e-5f);
    assert(fabsf(c - (-0.5f)) < 1e-5f);

    // alpha=0.0, beta=1.0 -> a=0.0, b=sqrt(3)/2, c=-sqrt(3)/2
    float sqrt3_2 = sqrtf(3.0f) / 2.0f;
    inv_clarke_transform(0.0f, 1.0f, &a, &b, &c);
    assert(fabsf(a - 0.0f) < 1e-5f);
    assert(fabsf(b - sqrt3_2) < 1e-5f);
    assert(fabsf(c - (-sqrt3_2)) < 1e-5f);
}

void test_park_known_vectors(void) {
    float d = 0.0f, q = 0.0f;
    float theta = (float)M_PI / 4.0f; // 45 deg

    // alpha=1.0, beta=0.0 at theta=pi/4 -> d=cos(pi/4), q=-sin(pi/4)
    park_transform(1.0f, 0.0f, theta, &d, &q);
    assert(fabsf(d - cosf(theta)) < 1e-5f);
    assert(fabsf(q - (-sinf(theta))) < 1e-5f);

    // alpha=0.0, beta=1.0 at theta=pi/4 -> d=sin(pi/4), q=cos(pi/4)
    park_transform(0.0f, 1.0f, theta, &d, &q);
    assert(fabsf(d - sinf(theta)) < 1e-5f);
    assert(fabsf(q - cosf(theta)) < 1e-5f);
}

void test_invertibility_roundtrip(void) {
    // Test across a full 360-degree electrical cycle with varied amplitudes
    const int num_angles = 360;
    const float amplitudes[] = { 0.1f, 1.0f, 5.0f, 12.5f, 24.0f };
    const int num_amps = sizeof(amplitudes) / sizeof(amplitudes[0]);

    for (int a_idx = 0; a_idx < num_amps; a_idx++) {
        float I_peak = amplitudes[a_idx];
        for (int i = 0; i < num_angles; i++) {
            float theta = (float)i * (2.0f * (float)M_PI / (float)num_angles);

            // Balanced 3-phase sinusoidal set
            float a = I_peak * cosf(theta);
            float b = I_peak * cosf(theta - 2.0f * (float)M_PI / 3.0f);
            float c = I_peak * cosf(theta + 2.0f * (float)M_PI / 3.0f);

            // Forward Clarke
            float alpha = 0.0f, beta = 0.0f;
            clarke_transform(a, b, c, &alpha, &beta);

            // Inverse Clarke round-trip
            float a_rec = 0.0f, b_rec = 0.0f, c_rec = 0.0f;
            inv_clarke_transform(alpha, beta, &a_rec, &b_rec, &c_rec);
            assert(fabsf(a - a_rec) < 1e-5f * (1.0f + I_peak));
            assert(fabsf(b - b_rec) < 1e-5f * (1.0f + I_peak));
            assert(fabsf(c - c_rec) < 1e-5f * (1.0f + I_peak));

            // Forward Park
            float d = 0.0f, q = 0.0f;
            park_transform(alpha, beta, theta, &d, &q);

            // Inverse Park round-trip
            float alpha_rec = 0.0f, beta_rec = 0.0f;
            inv_park_transform(d, q, theta, &alpha_rec, &beta_rec);
            assert(fabsf(alpha - alpha_rec) < 1e-5f * (1.0f + I_peak));
            assert(fabsf(beta - beta_rec) < 1e-5f * (1.0f + I_peak));

            // Full round-trip: (d, q) -> (alpha, beta) -> (a, b, c)
            float a_full = 0.0f, b_full = 0.0f, c_full = 0.0f;
            inv_clarke_transform(alpha_rec, beta_rec, &a_full, &b_full, &c_full);
            assert(fabsf(a - a_full) < 1e-5f * (1.0f + I_peak));
            assert(fabsf(b - b_full) < 1e-5f * (1.0f + I_peak));
            assert(fabsf(c - c_full) < 1e-5f * (1.0f + I_peak));
        }
    }
}

int main(void) {
    printf("Running library transform unit tests...\n");
    test_clarke_known_vectors();
    test_inv_clarke_known_vectors();
    test_park_known_vectors();
    test_invertibility_roundtrip();
    printf("All Clarke, Park, and Inverse Transform invertibility tests PASSED.\n");
    return 0;
}

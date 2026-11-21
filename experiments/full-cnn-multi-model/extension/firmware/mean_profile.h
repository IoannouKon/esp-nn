#pragma once

#include <cstdint>

#include "esp_cpu.h"
#include "esp_timer.h"

struct MeanMeasurement {
    uint32_t calls = 0;
    uint32_t cycles = 0;
    int64_t us = 0;
};

extern bool profile_mean;
extern MeanMeasurement mean_measurement;

class MeanTimer {
public:
    MeanTimer() : start_cycles_(esp_cpu_get_cycle_count()), start_us_(esp_timer_get_time()) {}

    MeanMeasurement Read() const {
        const int64_t us = esp_timer_get_time() - start_us_;
        const uint32_t cycles = esp_cpu_get_cycle_count() - start_cycles_;
        return {1, cycles, us};
    }

private:
    const uint32_t start_cycles_;
    const int64_t start_us_;
};

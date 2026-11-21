#pragma once

#include "tensorflow/lite/micro/micro_common.h"

TFLMRegistration RegisterEspNnGlobalMean();

#ifdef CNN_MEAN_STRESS_ONLY
bool ValidateEspNnGlobalMean();
#endif

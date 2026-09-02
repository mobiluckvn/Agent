#ifndef LOGIC_PID_H
#define LOGIC_PID_H

#include <stdbool.h>

void pid_set_tunings(float kp, float ki, float kd);
float pid_compute(float angle, float pid_setpoint, bool is_running);

// Helper functions for testing
float pid_get_self_balance_setpoint(void);
float pid_get_i_mem(void);
float pid_get_last_d_error(void);
void pid_reset_state_for_test(void);

#endif // LOGIC_PID_H

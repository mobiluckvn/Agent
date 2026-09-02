#include "logic_pid.h"

static float pid_p_gain = 12.0f;
static float pid_i_gain = 0.4f;
static float pid_d_gain = 10.0f;

static float pid_i_mem = 0.0f;
static float pid_last_d_error = 0.0f;
static float pid_output = 0.0f;
static float self_balance_setpoint = 0.0f;
static bool latched_stop = false;

void pid_set_tunings(float kp, float ki, float kd) {
    pid_p_gain = kp;
    pid_i_gain = ki;
    pid_d_gain = kd;
}

float pid_compute(float angle, float pid_setpoint, bool is_running) {
    if (!is_running) {
        latched_stop = false;
    }
    
    if (angle > 30.0f || angle < -30.0f) {
        latched_stop = true;
    }
    
    if (!is_running || latched_stop) {
        pid_output = 0.0f;
        pid_i_mem = 0.0f;
        return 0.0f;
    }
    
    float pid_error_temp = angle - self_balance_setpoint - pid_setpoint;
    
    if (pid_output > 10.0f || pid_output < -10.0f) {
        pid_error_temp += pid_output * 0.015f;          // hàm phanh
    }
    
    pid_i_mem += pid_i_gain * pid_error_temp;
    if (pid_i_mem >  400.0f) pid_i_mem =  400.0f;            // kẹp tích phân
    if (pid_i_mem < -400.0f) pid_i_mem = -400.0f;
    
    // NOTE: Derivative is taken on error, which causes derivative kick if setpoint jumps.
    // This is intentional for this balancing robot as the setpoint changes are gradual (±0.0015 per loop).
    // Must be reviewed if forward/backward commands are added causing setpoint step changes.
    pid_output = pid_p_gain * pid_error_temp
               + pid_i_mem
               + pid_d_gain * (pid_error_temp - pid_last_d_error);
               
    if (pid_output >  400.0f) pid_output =  400.0f;
    if (pid_output < -400.0f) pid_output = -400.0f;
    
    pid_last_d_error = pid_error_temp;
    
    if (pid_output < 5.0f && pid_output > -5.0f) {
        pid_output = 0.0f;   // vùng chết
    }
    
    if (pid_setpoint == 0.0f) {
        if (pid_output < 0.0f) self_balance_setpoint += 0.0015f;
        if (pid_output > 0.0f) self_balance_setpoint -= 0.0015f;
    }
    
    return pid_output;
}

float pid_get_self_balance_setpoint(void) {
    return self_balance_setpoint;
}

float pid_get_i_mem(void) {
    return pid_i_mem;
}

float pid_get_last_d_error(void) {
    return pid_last_d_error;
}

void pid_reset_state_for_test(void) {
    pid_i_mem = 0.0f;
    pid_last_d_error = 0.0f;
    pid_output = 0.0f;
    self_balance_setpoint = 0.0f;
    latched_stop = false;
}

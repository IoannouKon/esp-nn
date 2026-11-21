// EXP-MEAN: ESP32-S3 PIE 16-channel signed INT8 spatial reduction.
// ABI: a2=input, a3=elements, a4=channels/byte stride, a5=raw output.
// Preconditions (enforced by C): elements in [1,4095], channels%16==0,
// input and raw buffer 16-byte aligned.
// QACC = 16 independent 20-bit signed sums. The stored layout matches
// the TIE728 QACC dump convention used by ESP-DL.

    .text
    .align 4
    .type esp_nn_mean_s8_16ch_qacc, @function
    .global esp_nn_mean_s8_16ch_qacc
esp_nn_mean_s8_16ch_qacc:
    entry   a1,32

    // Broadcast signed INT8 +1 into all 16 lanes.
    movi.n  a8,1
    s32i.n  a8,a1,0
    ee.vldbc.8 q1,a1
    ee.zero.qacc

    mov.n   a8,a2
    loopgtz a3,.Lmean_qacc_done
        ee.vld.128.xp q0,a8,a4
        ee.vmulas.s8.qacc q0,q1
.Lmean_qacc_done:

    // 64-byte dump: low-half 20 bytes; 12-byte gap; high-half 20 bytes.
    // The next 128-bit dump requires 16-byte alignment of its address.
    ee.st.qacc_l.l.128.ip a5,16
    ee.st.qacc_l.h.32.ip  a5,16
    ee.st.qacc_h.l.128.ip a5,16
    ee.st.qacc_h.h.32.ip  a5,4
    retw.n

    .size esp_nn_mean_s8_16ch_qacc, . - esp_nn_mean_s8_16ch_qacc

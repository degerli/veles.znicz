#include "gradient_descent_common.cl"


#if USE_ORTHO > 0
#include "weights_ortho.cl"
#endif


/// @brief Calculate gradient for weights update.
/// @param err_output Backpropagated error.
/// @param input Layer input.
/// @param weights Layer weights.
/// @param gradient Computed gradient.
/// @param lr learning_rate.
/// @param factor_l12 lnorm_factor.
/// @param l1_vs_l2 how much to prefer l1 over l2 (from [0, 1]).
/// @param gradient_moment Moment for gradient.
/// @details gradient = previous_gradient * gradient_moment -
///                     lr * (err_output * h +
///                     factor_l12 * ((1 - l1_vs_l2) * weights + 0.5 * l1_vs_l2 * sign(weights)).
///          Should be defined externally:
///          A_BLOCK_SIZE, B_BLOCK_SIZE, COMMON_BLOCK_SIZE - for matrix multiplication,
///          BATCH - minibatch size,
///          H - input size,
///          Y - output size.
__kernel __attribute__((reqd_work_group_size(B_BLOCK_SIZE, A_BLOCK_SIZE, 1)))
void weights_update(__global const dtype    /* IN */    *err_output,
                    __global const dtype    /* IN */    *input,
                    __global dtype     /* IN, OUT */    *weights,
                    __global dtype     /* IN, OUT */    *gradient,
                    const dtype             /* IN */    lr,
                    const dtype             /* IN */    factor_l12,
                    const dtype             /* IN */    l1_vs_l2,
                    const dtype             /* IN */    gradient_moment
#if USE_ORTHO > 0
                    , const dtype           /* IN */    factor_ortho,
                    __global const dtype    /* IN */    *col_sums
#endif
                    ) {
  #if WEIGHTS_TRANSPOSED > 0
  #define A_WIDTH H
  #define B_WIDTH Y
  #define A input
  #define B err_output
  #else
  #define A_WIDTH Y
  #define B_WIDTH H
  #define A err_output
  #define B input
  #endif

  #define AB_COMMON BATCH

  #define A_COL
  #define B_COL

  #include "matrix_multiplication.cl"

  #undef A_COL
  #undef B_COL

  #undef A_WIDTH
  #undef B_WIDTH
  #undef AB_COMMON

  #undef A
  #undef B

  if (valid) {
    dtype weight = weights[idx];
    dtype gd = -lr * (sum + gradient_step_l12(weight, factor_l12, l1_vs_l2)
#if USE_ORTHO > 0
    #if WEIGHTS_TRANSPOSED > 0
               + gradient_step_ortho(weight, factor_ortho, get_global_id(1), Y, col_sums)
    #else
               + gradient_step_ortho(weight, factor_ortho, get_global_id(0), Y, col_sums)
    #endif
#endif
               );
    #if STORE_GRADIENT > 0
    gd += gradient[idx] * gradient_moment;
    gradient[idx] = gd;
    #endif
    #if APPLY_GRADIENT > 0
    weights[idx] = weight + gd;
    #endif
  }
}
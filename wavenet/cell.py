"""
RNN cells for WaveNet components.
"""

from tensorflow.contrib.rnn import RNNCell  # pylint: disable=E0611


class ConvCell(RNNCell):
    """
    A recurrent cell that applies a dilated convolution
    using a caching mechanism to prevent re-computation.
    """

    def __init__(self, conv):
        """
        Create a ConvCell from a Conv instance.
        """
        self.conv = conv

    @property
    def state_size(self):
        return (tf.TensorShape([self.conv.in_depth]),) * (self.conv.receptive_field - 1)

    @property
    def output_size(self):
        return self.conv.in_depth

    def zero_state(self, batch_size, dtype):
        """
        Generate an all-zero cache for the cell.
        """
        zeros = tf.zeros([batch_size, self.conv.in_depth], dtype=dtype)
        return (zeros,) * (self.conv.receptive_field - 1)

    def call(self, inputs, state):
        old_inputs = state[0]
        new_cache = state[1:] + (inputs,)
        return self.conv.apply_once(old_inputs, inputs)

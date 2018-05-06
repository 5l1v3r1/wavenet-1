"""
WaveNet model definition.
"""

from abc import ABC, abstractmethod, abstractproperty

import tensorflow as tf


class Model(ABC):
    """
    A generic WaveNet model.
    """
    @abstractproperty
    def receptive_field(self):
        """
        Get the receptive field of the model.

        This is the number of timesteps back the model can
        see. For example, if the model can see the current
        timestep and the two previous timesteps, then the
        receptive field is 3.
        """
        pass

    @abstractmethod
    def apply(self, inputs):
        """
        Apply the model to a batch of inputs.

        The batch size and number of timesteps needn't be
        known while building the graph.

        Args:
          inputs: a [batch x timesteps x channels] Tensor.

        Returns:
          A new [batch x timesteps x channels] Tensor.
        """
        pass


class Conv(Model):
    """
    A dilated convolution layer.
    """

    def __init__(self, in_depth, dilation, hidden_size=None, dtype=tf.float32):
        """
        Create a new Layer.

        Args:
          in_depth: the number of input channels.
          dilation: the base 2 logarithm of the dilation.
            0 means undilated, 1 means dilated by a factor
            of 2, etc.
          hidden_size: if specified, this is the number of
            channels in the dilated convolution output,
            before the 1x1 projection brings the number of
            channels back to in_depth. If None, then
            in_depth is used.
          dtype: the DType for the convolutional kernels.
        """
        self.in_depth = in_depth
        self.dilation = dilation
        self.hidden_size = hidden_size or in_depth
        with tf.variable_scope(None, default_name='layer'):
            self.filter_kernel = tf.get_variable('filter_kernel',
                                                 dtype=dtype,
                                                 shape=(2 * self.in_depth, self.hidden_size))
            self.gate_kernel = tf.get_variable('gate_kernel',
                                               dtype=dtype,
                                               shape=(2 * self.in_depth, self.hidden_size))
            self.projection = tf.get_variable('projection',
                                              dtype=dtype,
                                              shape=(self.hidden_size, self.in_depth))

    @property
    def receptive_field(self):
        return 2 ** self.dilation + 1

    def apply(self, inputs):
        assert inputs.get_shape()[-1].value == self.in_depth, 'incorrect number of input channels'
        assert len(inputs.get_shape()) == 3, 'invalid input shape'

        padded_input = tf.pad(inputs, [[0, 0], [self.receptive_field - 1, 0], [0, 0]])
        shifted = padded_input[:, :-(self.receptive_field - 1)]
        # [batch x timesteps x (channels * 2)].
        joined = tf.concat([shifted, inputs], axis=-1)
        filters = tf.tanh(_sequence_matmul(joined, self.filter_kernel))
        gates = tf.sigmoid(_sequence_matmul(joined, self.gate_kernel))
        projected = _sequence_matmul(filters * gates, self.projection)
        return projected + inputs


class Network(Model):
    """
    A description of a full WaveNet model.
    """

    def __init__(self, layers):
        """
        Create a Network.

        Args:
          layers: a sequence of layers, ordered from the
            input to the output.
        """
        self.layers = layers

    @property
    def receptive_field(self):
        assert len(self.layers) > 0
        current_field = self.layers[0].receptive_field
        for layer in self.layers[1:]:
            # Subtract one because layer.receptive_field
            # already counts one of the same timesteps as
            # current_field.
            current_field += layer.receptive_field - 1
        return current_field

    def apply(self, inputs):
        outputs = inputs
        for layer in self.layers:
            outputs = layer.apply(outputs)
        return outputs


def _sequence_matmul(seq, matrix):
    """
    Apply a matrix to the inner dimension of a Tensor of
    shape [batch x timesteps x channels].
    """
    flat = tf.reshape(seq, [-1, seq.get_shape()[-1]])
    flat_res = tf.matmul(flat, matrix)
    shape = [seq.get_shape()[i] or tf.shape(seq)[i] for i in [0, 1]] + [matrix.get_shape()[-1]]
    return tf.reshape(flat_res, shape)
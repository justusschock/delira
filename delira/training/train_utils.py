import numpy as np

from delira import get_backends
from ..utils.decorators import dtype_func


def _check_and_correct_zero_shape(arg):
    """
    Corrects the shape of numpy array to be at least 1d and returns the
    argument as is otherwise

    Parameters
    ----------
    arg : Any
        the argument which must be corrected in its shape if it's
        zero-dimensional

    Returns
    -------
    Any
        argument (shape corrected if necessary)
    """
    if isinstance(arg, np.ndarray) and arg.shape == ():
        arg = arg.reshape(1)
    return arg


def convert_batch_to_numpy_identity(*args, **kwargs):
    """
    Corrects the shape of all zero-sized numpy arrays to be at least 1d

    Parameters
    ----------
    *args :
        positional arguments of potential arrays to be corrected
    **kwargs :
        keyword arguments of potential arrays to be corrected

    Returns
    -------

    """
    args = list(args)

    for idx, arg in args:
        args[idx] = _check_and_correct_zero_shape(arg)

    for key, val in kwargs.items():
        kwargs[key] = _check_and_correct_zero_shape(val)

    return args, kwargs


if "TORCH" in get_backends():
    import torch

    from ..utils.decorators import torch_tensor_func, torch_module_func

    @dtype_func(float)
    def float_to_pytorch_tensor(f: float):
        """
        Converts a single float to a PyTorch Float-Tensor

        Parameters
        ----------
        f : float
            float to convert

        Returns
        -------
        torch.Tensor
            converted float

        """
        return torch.from_numpy(np.array([f], dtype=np.float32))

    @torch_module_func
    def create_optims_default_pytorch(model, optim_cls, **optim_params):
        """
        Function to create a optimizer dictionary
        (in this case only one optimizer for the whole network)

        Parameters
        ----------
        model : :class:`AbstractPyTorchNetwork`
            model whose parameters should be updated by the optimizer
        optim_cls :
            Class implementing an optimization algorithm
        **optim_params :
            Additional keyword arguments (passed to the optimizer class

        Returns
        -------
        dict
            dictionary containing all created optimizers
        """
        return {"default": optim_cls(model.parameters(), **optim_params)}

    @torch_module_func
    def create_optims_gan_default_pytorch(model, optim_cls, **optim_params):
        """
        Function to create a optimizer dictionary
        (in this case two optimizers: One for the generator,
        one for the discriminator)

        Parameters
        ----------
        model : :class:`AbstractPyTorchNetwork`
            model whose parameters should be updated by the optimizer
        optim_cls :
            Class implementing an optimization algorithm
        optim_params :
            Additional keyword arguments (passed to the optimizer class

        Returns
        -------
        dict
            dictionary containing all created optimizers
        """
        return {"gen": optim_cls(model.gen.parameters(), **optim_params),
                "discr": optim_cls(model.discr.parameters(), **optim_params)}

    def convert_torch_tensor_to_npy(*args, **kwargs):
        """
        Function to convert all torch Tensors to numpy arrays and
        reshape zero-size tensors

        Parameters
        ----------
        *args :
            arbitrary positional arguments
        **kwargs :
            arbitrary keyword arguments

        Returns
        -------
        Iterable
            all given positional arguments (converted if necessary)

        dict
            all given keyword arguments (converted if necessary)

        """
        args = [_arg.detach().cpu().numpy() for _arg in args
                if isinstance(_arg, torch.Tensor)]
        for k, v in kwargs.items():
            if isinstance(v, torch.Tensor):
                kwargs[k] = v.detach().cpu().numpy()

        return convert_batch_to_numpy_identity(*args, **kwargs)

if "TF" in get_backends():
    import tensorflow as tf

    def create_optims_default_tf(optim_cls, **optim_params):
        """
        Function to create a optimizer dictionary
        (in this case only one optimizer)

        Parameters
        ----------
        optim_cls :
            Class implementing an optimization algorithm
        **optim_params :
            Additional keyword arguments (passed to the optimizer class)

        Returns
        -------
        dict
            dictionary containing all created optimizers
        """
        return {"default": optim_cls(**optim_params)}

    def initialize_uninitialized(sess):
        """
        Function to initialize only uninitialized variables in a session graph

        Parameters
        ----------

        sess : tf.Session()
        """

        global_vars = tf.global_variables()
        is_not_initialized = sess.run(
            [tf.is_variable_initialized(var) for var in global_vars])

        not_initialized_vars = [v for (v, f) in zip(
            global_vars, is_not_initialized) if not f]

        if not_initialized_vars:
            sess.run(tf.variables_initializer(not_initialized_vars))

    def _convert_tensor_to_npy_eager(tensor):
        """
        Convert tensor in eager mode to numpy

        Parameters
        ----------
        tensor : arraylike or tf.Tensor

        Returns
        -------
        arraylike
            converted tensor

        """
        if isinstance(tensor, tf.Tensor):
            return tensor.numpy()
        return tensor

    def convert_tf_tensor_to_npy(*args, **kwargs):
        """
        Function to convert all tf Tensors to numpy arrays
        and reshape zero-size tensors

        Parameters
        ----------
        *args :
            arbitrary positional arguments
        **kwargs :
            arbitrary keyword arguments

        Returns
        -------
        Iterable
            all given positional arguments (converted if necessary)

        dict
            all given keyword arguments (converted if necessary)

        """
        eager = tf.executing_eagerly()

        # eager conversion
        if eager:
            convert_fn = _convert_tensor_to_npy_eager
        else:
            # no conversion needed since tensors should always be numpy arrays
            def convert_fn(tensor):
                return tensor
        args = list(args)

        for idx, _arg in args:
            args[idx] = convert_fn(_arg)

        for k, v in kwargs.items():
            kwargs[k] = convert_fn(v)
        return convert_batch_to_numpy_identity(*args, **kwargs)


    from tensorflow.python.eager.context import context, EAGER_MODE, GRAPH_MODE

    # hacky switch function
    def switch_tf_execution_mode(mode: str):
        mode = mode.lower()

        mode = mode.replace("_mode", "")

        if mode == "eager":
            _mode = EAGER_MODE
        elif mode == "graph":
            _mode = GRAPH_MODE
        else:
            raise ValueError("Invalid Execution mode given: %s" % mode)

        ctx = context()._eager_context
        ctx.mode = _mode
        ctx.is_eager = _mode == EAGER_MODE


if "CHAINER" in get_backends():
    import chainer
    from ..models.chainer_parallel import DataParallelOptimizer

    def convert_chainer_tensor_to_npy(*args, **kwargs):
        """
        Converts all chainer variables in args and kwargs to numpy array

        Parameters
        ----------
        *args :
            positional arguments of arbitrary number and type
        **kwargs :
            keyword arguments of arbitrary number and type

        Returns
        -------
        list
            converted positional arguments
        dict
            converted keyboard arguments
        """
        args = list(args)
        for idx, arg in enumerate(args):
            if isinstance(arg, chainer.Variable):
                args[idx] = arg.to_cpu().array

        for k, v in kwargs.items():
            if isinstance(v, chainer.Variable):
                kwargs[k] = v.to_cpu().array

        return convert_batch_to_numpy_identity(*args, **kwargs)

    def create_optims_default_chainer(model, optim_cls, **optimizer_params):
        """
        Default function to create a single optimizer for chainer
        (also supports Data-Parallel)

        Parameters
        ----------
        model : :class:`chainer.Link`
            the model, which should be updated by the optimizer
        optim_cls : :class:`chainer.Optimizer`
            the optimizer class implementing the actual parameter update
        optimizer_params : dict
            the params used for initializing an instance of ``optim_cls``

        Returns
        -------
        dict
            dictionary containing the created optimizer (key: "default")

        """
        if issubclass(optim_cls, DataParallelOptimizer):
            optim = optim_cls.from_optimizer_class(**optimizer_params)

        else:
            optim = optim_cls(**optimizer_params)

        optim.setup(model)

        return {"default": optim}


import os
import logging
import numpy as np
from tqdm.auto import tqdm
import tensorflow as tf
from batchgenerators.dataloading import MultiThreadedAugmenter
from .callbacks import AbstractCallback
from .base_trainer import BaseNetworkTrainer
from .train_utils import create_optims_default_tf as create_optims_default
from .train_utils import initialize_uninitialized
from .train_utils import convert_tf_tensor_to_npy
from ..io import tf_load_checkpoint, tf_save_checkpoint

logger = logging.getLogger(__name__)


class TfNetworkTrainer(BaseNetworkTrainer):
    """
    Train and Validate a Network

    See Also
    --------
    :class:`AbstractNetwork`

    """

    def __init__(self,
                 network,
                 save_path,
                 key_mapping, 
                 losses: dict,
                 optimizer_cls,
                 optimizer_params={},
                 train_metrics={},
                 val_metrics={},
                 lr_scheduler_cls=None,
                 lr_scheduler_params={},
                 gpu_ids=[],
                 save_freq=1,
                 optim_fn=create_optims_default,
                 logging_type="tensorboardx",
                 logging_kwargs={},
                 fold=0,
                 callbacks=[],
                 start_epoch=1,
                 metric_keys=None,
                 convert_batch_to_npy_fn=convert_tf_tensor_to_npy,
                 **kwargs
                 ):
        """

        Parameters
        ----------
        network : :class:`AbstractTfNetwork`
            the network to train
        save_path : str
            path to save networks to
        key_mapping : dict
            a dictionary containing the mapping from the ``data_dict`` to 
            the actual model's inputs.
            E.g. if a model accepts one input named 'x' and the data_dict 
            contains one entry named 'data' this argument would have to 
            be ``{'x': 'data'}``
        losses : dict
            dictionary containing the training losses
        optimizer_cls : subclass of tf.train.Optimizer
            optimizer class implementing the optimization algorithm of choice
        optimizer_params : dict
            keyword arguments passed to optimizer during construction
        train_metrics : dict, optional
            metrics, which will be evaluated during train phase 
            (should work on numpy arrays)
        val_metrics : dict, optional
            metrics, which will be evaluated during test phase 
            (should work on numpy arrays)
        lr_scheduler_cls : Any
            learning rate schedule class: must implement step() method
        lr_scheduler_params : dict
            keyword arguments passed to lr scheduler during construction
        gpu_ids : list
            list containing ids of GPUs to use; if empty: use cpu instead
        save_freq : int
            integer specifying how often to save the current model's state.
            State is saved every state_freq epochs
        optim_fn : function
            creates a dictionary containing all necessary optimizers
        logging_type : str or callable
            the type of logging. If string: it must be one of
            ["visdom", "tensorboardx"]
            If callable: it must be a logging handler class
        logging_kwargs : dict
            dictionary containing all logging keyword arguments
        fold : int
            current cross validation fold (0 per default)
        callbacks : list
            initial callbacks to register
        start_epoch : int
            epoch to start training at
        metric_keys : dict
            dict specifying which batch_dict entry to use for which metric as 
            target; default: None, which will result in key "label" for all 
            metrics
        convert_batch_to_npy_fn : type, optional
            function converting a batch-tensor to numpy, per default this is
            the identity function
        **kwargs :
            Additional keyword arguments

        """

        super().__init__(
            network, save_path, losses, optimizer_cls, optimizer_params,
            train_metrics, val_metrics, lr_scheduler_cls, key_mapping,
            lr_scheduler_params, gpu_ids, save_freq, optim_fn, logging_type,
            logging_kwargs, fold, callbacks, start_epoch, metric_keys,
            convert_batch_to_npy_fn)

        self._setup(network, optim_fn, optimizer_cls, optimizer_params,
                    lr_scheduler_cls, lr_scheduler_params,
                    convert_batch_to_npy_fn, gpu_ids)

        for key, val in kwargs.items():
            setattr(self, key, val)

    def _setup(self, network, optim_fn, optimizer_cls, optimizer_params,
               lr_scheduler_cls, lr_scheduler_params, convert_batch_to_npy_fn,
               gpu_ids):
        """
        Defines the Trainers Setup

        Parameters
        ----------
        network : instance of :class: `AbstractTfNetwork`
            the network to train
        optim_fn : function
            creates a dictionary containing all necessary optimizers
        optimizer_cls : subclass of tf.train.Optimizer
            optimizer class implementing the optimization algorithm of choice
        optimizer_params : dict
        lr_scheduler_cls : Any
            learning rate schedule class: must implement step() method
        lr_scheduler_params : dict
            keyword arguments passed to lr scheduler during construction
        convert_batch_to_npy_fn : type, optional
            function converting a batch-tensor to numpy, per default this is
            the identity function
        gpu_ids : list
            list containing ids of GPUs to use; if empty: use cpu instead
        """

        # TODO: implement multi-GPU and single GPU training with help of
        #  https://www.tensorflow.org/api_docs/python/tf/keras/utils/multi_gpu_model
        #  note: might be bugged in combination with sess.run https://github.com/tensorflow/tensorflow/issues/21788
        #  and https://www.tensorflow.org/api_docs/python/tf/keras/models/clone_model

        """
        if gpu_ids and tf.test.is_gpu_available():
            assert len(gpu_ids) <= len(get_available_gpus()), "more GPUs 
            specified than available"
            self.use_gpu = True
            if len(gpu_ids) > 1:
                logger.warning(
                    "multi-GPU training not yet tested!")

                network.model = tf.keras.utils.multi_gpu_model(
                                        network.model,
                                        len(gpu_ids),
                                        cpu_merge=True,
                                        cpu_relocation=False)
            else:
                network.models = tf.keras.models.clone_model(network.model)
        else:
            self.use_gpu = False
        """

        self.optimizers = optim_fn(optimizer_cls, **optimizer_params)

        super()._setup(network, lr_scheduler_cls, lr_scheduler_params, gpu_ids,
                       convert_batch_to_npy_fn, lambda x: x)

        self.use_gpu = True

        self.module._add_losses(self.losses)
        self.module._add_optims(self.optimizers)
        # check for unitialized variables
        initialize_uninitialized(self.module._sess)

    def _at_training_end(self):
        """
        Defines Behaviour at end of training: Loads best model if available

        Returns
        -------
        :class:`AbstractTfNetwork`
            best network

        """
        if os.path.isfile(os.path.join(self.save_path, 
                                       'checkpoint_best.meta')):

            # load best model and return it. Since the state is hidden in the 
            # graph, we don't actually need to use
            # self.update_state.
            self.update_state(os.path.join(self.save_path,
                                           'checkpoint_best')
                              )

        return self.module

    def _train_single_epoch(self, batchgen: MultiThreadedAugmenter, epoch,
                            verbose=False):
        """
        Trains the network a single epoch

        Parameters
        ----------
        batchgen : MultiThreadedAugmenter
            Generator yielding the training batches
        epoch : int
            current epoch

        """
        self.module.training = True

        return super()._train_single_epoch(batchgen, epoch, verbose=verbose)

    def predict_data_mgr(self, datamgr, batch_size=None, metrics={},
                         metric_keys={}, verbose=False):
        """
        Defines a routine to predict data obtained from a batchgenerator

        Parameters
        ----------
        datamgr : :class:`BaseDataManager`
            Manager producing a generator holding the batches
        batchsize : int
            Artificial batchsize (sampling will be done with batchsize
            1 and sampled data will be stacked to match the artificial
            batchsize)(default: None)
        metrics : dict
            the metrics to calculate
        metric_keys : dict
            the ``batch_dict`` items to use for metric calculation
        verbose : bool
            whether to show a progress-bar or not, default: False

        """
        self.module.training = False

        return super().predict_data_mgr(datamgr, batch_size, metrics,
                                        metric_keys, verbose=verbose)

    def save_state(self, file_name, *args, **kwargs):
        """
        saves the current state via :func:`delira.io.tf.save_checkpoint`

        Parameters
        ----------
        file_name : str
            filename to save the state to
        """
        tf_save_checkpoint(file_name, self.module)

    def load_state(self, file_name, *args, **kwargs):
        """
        Loads the new state from file via :func:`delira.io.tf.load_checkpoint`

        Parameters
        ----------
        file_name : str
            the file to load the state from
        Returns
        -------

        """
        return tf_load_checkpoint(file_name, self.module)

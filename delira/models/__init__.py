from delira import get_backends
from .abstract_network import AbstractNetwork

if "TORCH" in get_backends():
    from .abstract_network import AbstractPyTorchNetwork, \
        AbstractTorchScriptNetwork
    from .classification import VGG3DClassificationNetworkPyTorch, \
        ClassificationNetworkBasePyTorch

    from .segmentation import UNet2dPyTorch, UNet3dPyTorch

    from .gan import GenerativeAdversarialNetworkBasePyTorch

if "TF" in get_backends():
    from .abstract_network import AbstractTfNetwork, AbstractTfEagerNetwork
    from .classification import ClassificationNetworkBaseTf

if "CHAINER" in get_backends():
    from .abstract_network import AbstractChainerNetwork

if "SKLEARN" in get_backends():
    from .abstract_network import SklearnEstimator

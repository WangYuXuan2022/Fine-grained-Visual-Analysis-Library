# Copyright (c) 2022-present, BUPT-PRIS.

"""
    build.py provides various apis for building a training or evaluation system fast.
"""

import torch
from torch import nn
import torch.optim as optim
from torch.optim.optimizer import Optimizer
from torch.utils.data import Sampler
import torchvision.transforms as T
import typing as t
from yacs.config import CfgNode

from fgvclib.configs.utils import turn_list_to_dict as tltd
from fgvclib.criterions import get_criterion
from fgvclib.datasets import get_dataset
from fgvclib.datasets.datasets import FGVCDataset
from fgvclib.samplers import get_sampler
from fgvclib.metrics import get_metric
from fgvclib.metrics.metrics import NamedMetric
from fgvclib.models.sotas import get_model
from fgvclib.models.sotas.sota import FGVCSOTA
from fgvclib.models.backbones import get_backbone
from fgvclib.models.encoders import get_encoder
from fgvclib.models.necks import get_neck
from fgvclib.models.heads import get_head
from fgvclib.optimizers import get_optimizer
from fgvclib.transforms import get_transform
from fgvclib.utils.logger import get_logger, Logger
from fgvclib.utils.interpreter import get_interpreter, Interpreter
from fgvclib.utils.lr_schedules import get_lr_schedule, LRSchedule
from fgvclib.utils.update_function import get_update_function
from fgvclib.utils.evaluate_function import get_evaluate_function


def build_model(model_cfg: CfgNode) -> FGVCSOTA:
    r"""Build a FGVC model according to config.

    Args:
        model_cfg (CfgNode): The model config node of root config.
    Returns:
        fgvclib.models.sota.FGVCSOTA: The FGVC model.
    """

    backbone_builder = get_backbone(model_cfg.BACKBONE.NAME)
    backbone = backbone_builder(cfg=tltd(model_cfg.BACKBONE.ARGS))

    if model_cfg.ENCODER.NAME:
        encoder_builder = get_encoder(model_cfg.ENCODER.NAME)
        encoder = encoder_builder(cfg=tltd(model_cfg.ENCODER.ARGS))
    else:
        encoder = None

    if model_cfg.NECKS.NAME:
        neck_builder = get_neck(model_cfg.NECKS.NAME)
        necks = neck_builder(cfg=tltd(model_cfg.NECKS.ARGS))
    else:
        necks = None

    head_builder = get_head(model_cfg.HEADS.NAME)
    heads = head_builder(class_num=model_cfg.CLASS_NUM, cfg=tltd(model_cfg.HEADS.ARGS))

    criterions = {}
    for item in model_cfg.CRITERIONS:
        criterions.update({item["name"]: {"fn": build_criterion(item), "w": item["w"]}})
    
    model_builder = get_model(model_cfg.NAME)
    model = model_builder(cfg=model_cfg, backbone=backbone, encoder=encoder, necks=necks, heads=heads, criterions=criterions)
    
    return model

def build_logger(cfg: CfgNode) -> Logger:
    r"""Build a Logger object according to config.

    Args:
        cfg (CfgNode): The root config node.
    Returns:
        Logger: The Logger object.
    """

    return get_logger(cfg.LOGGER.NAME)(cfg)

def build_transforms(transforms_cfg: CfgNode) -> T.Compose:
    r"""Build transforms for train or test dataset according to config.

    Args:
        transforms_cfg (CfgNode): The root config node.
    Returns:
        PyTorch transforms.Compose: The transforms.Compose object in Pytorch.
    """

    return T.Compose([get_transform(item['name'])(item) for item in transforms_cfg])

def build_dataset(name:str, root:str, mode_cfg: CfgNode, mode:str, transforms:T.Compose) -> FGVCDataset:
    r"""Build a dataloader for training or evaluation.

    Args:
        name (str): The dataset name.
        root (str): The directory of dataset.
        mode_cfg (CfgNode): The mode config of the dataset config.
        mode (str): The split of the dataset.
        transforms (torchvision.transforms.Compose): Pytorch Transformer Compose.
    Returns:
        A FGVCDataset.
    """

    dataset = get_dataset(name)(root=root, mode=mode, download=True, transforms=transforms, positive=mode_cfg.POSITIVE)

    return dataset

def build_dataloader(dataset: FGVCDataset, mode_cfg: CfgNode, sampler=None, is_batch_sampler=False):
    r"""Build a dataloader for training or evaluation.

    Args:
        dataset (FGVCDataset): A FGVCDataset.
        mode_cfg (CfgNode): The mode config of the dataset config.
        sampler (Sampler): The dataloder sampler.
    Returns:
        DataLoader: A Pytorch Dataloader.
    """

    if is_batch_sampler:
        return torch.utils.data.DataLoader(
            dataset, 
            batch_sampler=sampler, 
            num_workers=mode_cfg.NUM_WORKERS,
            pin_memory=mode_cfg.PIN_MEMORY)
    
    else:
        return torch.utils.data.DataLoader(
            dataset, 
            batch_size=mode_cfg.BATCH_SIZE, 
            sampler=sampler, 
            num_workers=mode_cfg.NUM_WORKERS,
            pin_memory=mode_cfg.PIN_MEMORY)

def build_optimizer(optim_cfg: CfgNode, model:t.Union[nn.Module, nn.DataParallel]) -> Optimizer:
    r"""Build a optimizer for training.

    Args:
        optim_cfg (CfgNode): The optimizer config node of root config node.
    Returns:
        Optimizer: A Pytorch Optimizer.
    """

    params = list()
    model_attrs = ["backbone", "encoder", "necks", "heads"]

    # if isinstance(model, nn.DataParallel) or isinstance(model, nn.parallel.DistributedDataParallel):
    #     for attr in model_attrs:
    #         if getattr(model.module, attr) and optim_cfg.LR[attr]:
    #             params.append({
    #                 'params': getattr(model.module, attr).parameters(), 
    #                 'lr': optim_cfg.LR[attr]
    #             })
        
    # else:
    #     for attr in model_attrs:
    #         if getattr(model, attr) and optim_cfg.LR[attr]:
    #             params.append({
    #                 'params': getattr(model, attr).parameters(), 
    #                 'lr': optim_cfg.LR[attr]
    #             })

    

    if isinstance(model, nn.DataParallel) or isinstance(model, nn.parallel.DistributedDataParallel):
        m = model.module
    else:
        m = model
    for n, p in m.named_parameters():
        is_other = True
        if p.requires_grad:
            for attr in model_attrs:
                if n.__contains__(attr):
                    is_other = False
                    params.append({
                        'params': p, 
                        'lr': optim_cfg.LR[attr]
                    })

            if is_other:
                params.append({
                    'params': p, 
                    'lr': optim_cfg.LR["base"]
                })
        

    
    # for n, p in m.named_parameters():
        
    #     if n.__contains__()
    
    optimizer = get_optimizer(optim_cfg.NAME)(params, optim_cfg.LR.base, tltd(optim_cfg.ARGS))
    # optimizer = AdamW(params=params, lr=0.0001, weight_decay=5e-4)
    return optimizer

def build_criterion(criterion_cfg: CfgNode) -> nn.Module:
    r"""Build loss function for training.

    Args:
        criterion_cfg (CfgNode): The criterion config node of root config node.
    Returns:
        nn.Module: A loss function.
    """

    criterion_builder = get_criterion(criterion_cfg['name'])
    criterion = criterion_builder(cfg=tltd(criterion_cfg['args']))
    return criterion

def build_interpreter(model: nn.Module, cfg: CfgNode) -> Interpreter:
    r"""Build loss function for training.

    Args:
        cfg (CfgNode): The root config node.
    Returns:
        Interpreter: A Interpreter.
    """

    return get_interpreter(cfg.INTERPRETER.NAME)(model, cfg)

def build_metrics(metrics_cfg: CfgNode, use_cuda:bool=True) -> t.List[NamedMetric]:
    r"""Build metrics for evaluation.

    Args:
        metrics_cfg (CfgNode): The metric config node of root config node.
    Returns:
        t.List[NamedMetric]: A List of NamedMetric.
    """

    metrics = []
    for cfg in metrics_cfg:
        metric = get_metric(cfg["metric"])(name=cfg["name"], top_k=cfg["top_k"], threshold=cfg["threshold"])
        if use_cuda:
            metric = metric.cuda()
        metrics.append(metric)
    return metrics

def build_sampler(sampler_cfg: CfgNode) -> Sampler:
    r"""Build sampler for dataloader.

    Args:
        sampler_cfg (CfgNode): The sampler config node of root config node.
    Returns:
        Sampler: A dataset sampler.
    
    """
    
    return get_sampler(sampler_cfg.NAME)


def build_lr_schedule(optimizer, schedule_cfg: CfgNode, train_loader) -> LRSchedule:
    r"""Build lr_schedule for training.

    Args:
        schedule_cfg (CfgNode): The schedule config node of root config node.
    Returns:
        LRSchedule: A lr schedule.
    
    """
    batch_num_per_epoch = len(train_loader)

    return get_lr_schedule(schedule_cfg.NAME)(optimizer, batch_num_per_epoch, tltd(schedule_cfg.ARGS))

def build_update_function(cfg):
    r"""Build metrics for evaluation.

    Args:
        cfg (CfgNode): The root config node.
    Returns:
        function: A update model function.
    
    """
    
    return get_update_function(cfg.UPDATE_FUNCTION)


def build_evaluate_function(cfg):
    r"""Build metrics for evaluation.

    Args:
        cfg (CfgNode): The root config node.
    Returns:
        function: A evaluate model function.
    
    """
    return get_evaluate_function(cfg.EVALUATE_FUNCTION)

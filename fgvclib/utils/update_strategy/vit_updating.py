import numpy as np
import torch
from torch.autograd import Variable
import typing as t
from apex import amp as ap
from ..update_strategy import update_strategy
from fgvclib.criterions import compute_loss_value, detach_loss_value


@update_strategy("vit_update_strategy")
def vit_update_strategy(model, train_data, optimizer, use_cuda=True, amp=False, **kwargs) -> t.Dict:
    inputs, targets = train_data
    if use_cuda:
        inputs, targets = inputs.cuda(), targets.cuda()
    inputs, targets = Variable(inputs), Variable(targets)
    out, losses = model(inputs, targets)
    total_loss = compute_loss_value(losses)
    total_loss = total_loss.mean()
    if amp:
        with ap.scale_loss(total_loss, optimizer) as scaled_loss:
            scaled_loss.backward()
        torch.nn.utils.clip_grad_norm_(ap.master_params(optimizer), 1.0)
    else:
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    optimizer.zero_grad()
    losses_info = detach_loss_value(losses)
    losses_info.update({"iter_loss": total_loss.item()})

    return losses_info

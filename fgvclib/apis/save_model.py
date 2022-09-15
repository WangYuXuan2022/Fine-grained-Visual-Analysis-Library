import torch
import os
from fgvclib.utils.logger.logger import Logger

def save_model(cfg, model, logger: Logger):
    if cfg.WEIGHT.NAME:
        
        if not os.path.exists(cfg.WEIGHT.SAVE_DIR):
            try:
                os.mkdir(cfg.WEIGHT.SAVE_DIR)
            except:
                logger(f'Cannot create save dir under {cfg.WEIGHT.SAVE_DIR}')
                logger.close()
                exit()
        save_path = os.path.join(cfg.WEIGHT.SAVE_DIR, cfg.WEIGHT.NAME)
        torch.save(model.state_dict(), save_path)
        logger(f'Saving checkpoint to {save_path}')
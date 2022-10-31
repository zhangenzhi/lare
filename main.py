import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '1'
import argparse

from lare.tools.utils import get_yml_content
from lare.controller.utils import check_args_from_input_config

from lare.controller.base_controller import BaseController
from lare.controller.dist_controller import DistController
from lare.controller.multi_controller import MultiController

def args_parser():
    parser = argparse.ArgumentParser('lare_config')
    parser.add_argument(
        '--config',
        type=str,
        default='./scripts/configs/cifar10/lare.yaml',
        help='yaml config file path')
    args = parser.parse_args()
    return args
    
#TODO check dataset complete
def main():
    cmd_args = args_parser()
    yaml_configs = get_yml_content(cmd_args.config)
    yaml_configs = check_args_from_input_config(yaml_configs)
    
    if yaml_configs['experiment']['context'].get('multi-p'):
        ctr = MultiController(yaml_configs)
    elif yaml_configs['experiment']['context'].get('dist'):
        ctr = DistController(yaml_configs)
    else:
        ctr = BaseController(yaml_configs)
    
    ctr.run()
    
if __name__ == '__main__':
    main()


# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from dataclasses import dataclass
from .message_helper import MessageHelper
from .msgraph_helper import MSGraphHelper
from .lr_seen import LeastRecentlySeen
from .db_helper import DBHelper


__all__ = ["MessageHelper", "MSGraphHelper", "LeastRecentlySeen", "DBHelper", "Helpers"]


@dataclass
class Helpers:
    msg: MessageHelper
    graph: MSGraphHelper
    db: DBHelper

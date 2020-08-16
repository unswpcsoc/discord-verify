import pytest
from time import time
from unittest.mock import patch, AsyncMock, MagicMock
from iam.verify import (
    proc_begin, proc_restart
)
from iam.db import MemberKey, MemberNotFound, make_def_member_data
from iam.config import PREFIX, VER_ROLE

@pytest.mark.asyncio
async def test_begin_standard():
    db = MagicMock()
    member = AsyncMock()
    member.id = 0
    db.get_member_data = MagicMock(side_effect=MemberNotFound(member.id, ""))
    before_time = time()
    await proc_begin(db, None, None, member)

    call_args = db.set_member_data.call_args
    assert call_args[0][0] == member.id
    assert {k:v for k,v in call_args[0][1].items() if \
        k != MemberKey.VER_TIME} == {k:v for k,v in \
        make_def_member_data().items() if k != MemberKey.VER_TIME}
    assert call_args[0][1][MemberKey.VER_TIME] >= before_time and \
        call_args[0][1][MemberKey.VER_TIME] <= time()

    member.send.assert_awaited_with("What is your full name as it appears on "
        "your government-issued ID?\nYou can restart this verification "
        f"process at any time by typing `{PREFIX}restart`.")

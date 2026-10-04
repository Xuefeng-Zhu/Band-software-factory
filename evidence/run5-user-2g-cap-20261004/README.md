# User-requested 2 GiB OrbStack cap

The participant requested “Can we cap at 2gb”. At 22:49 UTC on October 4, 2026, the operator changed the global ceiling from 4096 to 2048 MiB, performed the required single stop/start, and restored the exact two previously running Run 5 owner containers. Immediate before/after inventories show no running Linux machines or other running containers. The original operation record includes arguments, start/end times, exit results and full container identities.

The current configured ceiling is **2048 MiB**. Docker reported **2,073,866,240 bytes** after activation. The earlier 4 GiB intervention remains historical evidence, not the current setting. The global ceiling includes VM overhead; this does not establish full 2 GiB availability to an application, application continuity or product acceptance. The cap must not be raised again without the participant's authorization.

This is a second disclosed post-dispatch operator infrastructure intervention. The operator did not send a BAND instruction, redispatch the task, edit product code or rerun product tests. QA was independently checking the fixed candidate on host processes. Those assertions do not establish organizer acceptance of either intervention.

A separate future-only factory patch, `af329946b1f8282ecddbdebdbdb397849ef80a06`, passed 253 utility tests including 13 new cases. Its one actual read-only query correctly rejected the 3072 MiB example minimum against the user's current cap. This expected failure proves the check detects insufficient total capacity; it is not a product failure or permission to resize the VM. [Ready-for-review PR](https://github.com/Xuefeng-Zhu/Tablekeeper-factory/pull/1). It has not been merged into the live frozen factory.

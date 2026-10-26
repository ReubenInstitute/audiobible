import sys
from scriptures import Scriptures
from Psalms import Psalms
from Parashot import Parashot
import biblemedia

scriptures = Scriptures()

kind, number, width, height = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])

if kind == 'psalm':
	psalms = Psalms(scriptures.bible)
	biblemedia.PsalmCoverDev(psalms[number - 1], (width, height)).export("build/covers")
elif kind == 'parashah':
	parashot = Parashot(scriptures.bible)
	biblemedia.ParashahCoverDev(parashot[number - 1], (width, height)).export("build/covers")

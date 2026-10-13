"""Owner voice for in-night decision points (GAME-V2-SPEC §12.1). No numbers here except placeholders filled
from the decision point / night_decision itself: {walk} walk-aways, {covers} covers, {op} won of month OP vs the
default option (vs_default_op) with {updown} = 늘었어요/줄었어요, {count} times a month. Unknown kinds fall back to lines built from the sim's own label / hint / downside text."""

PROMPT = {
    "walkin_group": ["예약도 없이 단체가 들어왔어요. 자리는 거의 찼는데 어떡하죠?",
                     "회식 손님이 우르르 들어왔어요. 받자니 줄 선 분들이 걸리고, 보내자니 아깝고요."],
    "staff_late": ["알바가 늦는대요. 피크 시간인데 큰일이네요.", "하필 저녁에 알바가 늦는다고 연락이 왔어요."],
    "meat_low": ["삼겹살이 떨어져 가요. 남은 손님들한테 다 못 낼 수도 있어요.", "벌써 고기가 바닥이 보여요. 어떻게 하죠?"],
    "rain_burst": ["갑자기 비가 쏟아져요. 야장 손님들 어떡하죠?", "소나기예요. 밖에 앉은 손님들이 젖고 있어요."],
    "blogger": ["블로거라는 분이 공짜로 먹고 후기를 써 주겠대요.", "맛집 블로거가 무료 식사를 제안했어요. 받을까요?"],
}
FORESIGHT = {   # kind -> option -> what the owner expects if he picks it
    ("walkin_group", "seat"): "받으면 계산서는 크게 나오는데, 줄 서 있던 손님들이 지쳐서 돌아갈 수 있어요",
    ("walkin_group", "turn_away"): "돌려보내면 지금 손님들 자리는 지키는데, 큰 매출을 놓치는 거죠",
    ("staff_late", "wait"): "제가 더 뛰면 돈은 안 드는데, 주문이 밀리고 저도 지칠 거예요",
    ("staff_late", "call_sub"): "대타를 부르면 금방 오긴 하는데, 일당이 꽤 나가요",
    ("meat_low", "swap"): "목살로 바꾸면 손님은 계속 받는데, 삼겹살 찾던 분들은 실망하겠죠",
    ("meat_low", "rush_buy"): "정육점에서 사 오면 메뉴는 지키는데, 비싸게 사고 제가 자리를 비워요",
    ("meat_low", "stop_seating"): "새 손님을 안 받으면 있는 분들한텐 좋은데, 늦게 오는 손님은 다 돌아가요",
    ("rain_burst", "move_inside"): "안으로 모시면 손님은 안 젖는데, 안쪽에서 기다리는 손님이 늘어요",
    ("rain_burst", "tarp"): "천막으로 버티면 안쪽 자리는 그대로인데, 밖에 계신 분들은 불편하시겠죠",
    ("blogger", "comp"): "대접하면 후기가 올라오긴 할 텐데, 원가도 들고 협찬 후기는 안 믿는 분도 있어요",
    ("blogger", "decline"): "거절하면 돈은 안 드는데, 노출 기회를 놓치고 서운한 글이 올라올 수도 있어요",
}
AFTERMATH = {   # kind -> option -> what happened (placeholders from the night_decision)
    ("walkin_group", "seat"): ["단체 손님 받았더니 계산서는 컸는데, 줄 서 있던 손님 {walk}팀이 기다리다 돌아갔어요",
                               "단체 받은 날은 정신없었어요. 그런 날이 한 달에 {count}번쯤이라 평소 대응보다 영업이익이 {op} {updown}",
                               "단체 테이블 붙여 드렸더니 홀이 꽉 찼어요. 밖에선 줄이 길어졌고요",
                               "회식 손님 받은 날은 매출은 좋은데 다른 손님 응대가 밀려요"],
    ("walkin_group", "turn_away"): ["단체 손님은 보냈어요. 자리는 지켰지만 큰 매출은 놓쳤죠",
                                    "회식 손님을 돌려보낸 게 좀 마음에 걸려요",
                                    "단체는 정중히 돌려보냈어요. 대신 기다리던 손님들은 금방 앉으셨죠",
                                    "자리가 모자라서 단체는 못 받았어요. 아쉽지만 홀은 편했어요"],
    ("staff_late", "wait"): ["알바 없이 버텼더니 주문이 밀리고 제가 많이 지쳤어요",
                             "제가 두 사람 몫을 했어요. 손님 몇 분은 기다리다 짜증을 내셨고요",
                             "알바 올 때까지 혼자 뛰었어요. 불판 갈아 드리는 게 늦었죠",
                             "일손이 모자란 저녁이었어요. 다음엔 대타를 부를까 싶어요"],
    ("staff_late", "call_sub"): ["대타를 불렀더니 저녁은 무사히 넘겼어요. 일당은 나갔지만요",
                                 "대타 덕분에 피크를 버텼어요",
                                 "급하게 대타를 구했어요. 돈은 들었어도 손님 응대는 괜찮았어요",
                                 "대타 부른 게 다행이었어요. 그날 손님이 많았거든요"],
    ("meat_low", "swap"): ["목살로 바꿔 냈더니 손님 {walk}팀은 그냥 가셨어요", "삼겹살 찾던 손님들이 많이 아쉬워했어요",
                           "삼겹살 대신 목살을 권해 드렸어요. 대부분은 괜찮다고 하셨어요",
                           "고기를 바꿔 내니 몇 분은 표정이 안 좋으셨어요"],
    ("meat_low", "rush_buy"): ["정육점에서 급히 사 왔더니 메뉴는 지켰는데, 원가가 비싸게 먹혔어요",
                               "고기 사러 뛰어갔다 왔어요. 그사이 홀이 좀 밀렸고요",
                               "급히 고기를 구해 와서 메뉴는 안 바꿨어요. 대신 남는 게 적었죠",
                               "동네 정육점 덕분에 삼겹살은 안 끊겼어요"],
    ("meat_low", "stop_seating"): ["새 손님을 안 받았더니 늦게 온 손님 {walk}팀이 돌아갔어요", "남은 손님한테만 집중했어요",
                                   "고기가 모자라서 일찍 문 앞을 막았어요",
                                   "있는 손님만 모셨어요. 문 앞에서 돌아서는 분들 보니 마음이 안 좋았어요"],
    ("rain_burst", "move_inside"): ["야장 손님을 안으로 모셨더니 안쪽 대기가 길어졌어요", "비 피해서 다 들어오시니 홀이 꽉 찼어요",
                                    "야장 테이블을 급히 안으로 옮겼어요. 정신없었죠",
                                    "비가 쏟아져서 밖에 계신 분들을 다 안으로 모셨어요"],
    ("rain_burst", "tarp"): ["천막으로 버텼더니 밖에 계신 분들이 좀 불편해하셨어요", "우산 들고 버티시느라 고생하셨죠",
                             "천막 치고 버텼어요. 안쪽 손님은 편하게 드셨고요",
                             "비 오는 야장도 나름 분위기 있다고 하시는 분도 있었어요"],
    ("blogger", "comp"): ["블로거 대접했더니 후기가 올라왔어요", "블로거한테 한 상 차려 드렸어요. 효과는 지켜봐야죠",
                         "블로거 분께 서비스로 드렸어요. 글이 잘 나오면 좋겠네요",
                         "협찬으로 한 상 내드렸어요. 원가는 좀 들었죠"],
    ("blogger", "decline"): ["블로거 제안은 정중히 거절했어요", "공짜 식사는 안 드렸어요. 서운해하시는 눈치였지만요",
                            "협찬은 안 받기로 했어요. 손님 후기로 가는 게 맞는 것 같아서요",
                            "블로거 제안은 넘겼어요. 괜히 신경 쓰이긴 했지만요"],
}
REVIEW_PARTY = {   # the decision's own party writes a review: kind -> option -> line
    ("walkin_group", "seat"): ["예약 없이 단체로 갔는데 받아 주셨어요", "단체로 갑자기 갔는데 테이블 붙여 주셨어요"],
    ("blogger", "comp"): ["초대받아 다녀왔어요", "사장님 초대로 맛보고 왔어요"],
}
REVIEW_AFFECTED = {   # another party whose night the decision changed: kind -> option -> (bad line, mild line)
    ("walkin_group", "seat"): ("단체 손님이 먼저 들어가서 한참 더 기다렸어요", "단체 손님 때문에 조금 더 기다렸어요"),
    ("staff_late", "wait"): ("알바가 안 왔는지 사장님 혼자 뛰어다니셨어요", "사장님이 혼자 바쁘게 뛰어다니셨어요"),
    ("meat_low", "swap"): ("삼겹살이 떨어져서 목살로 먹었어요", "삼겹살 대신 목살이 나왔어요"),
    ("meat_low", "stop_seating"): ("자리가 있어 보였는데 더 안 받는다고 해서 돌아왔어요", "늦게 가서 못 들어갈 뻔했어요"),
    ("rain_burst", "move_inside"): ("비 때문에 야장 손님이 들어와서 홀이 꽉 찼어요", "비 오는 날이라 안이 좀 붐볐어요"),
    ("rain_burst", "tarp"): ("비 오는데 천막 아래서 먹느라 불편했어요", "천막 아래서 먹었는데 그것도 운치 있었어요"),
    ("staff_late", "call_sub"): ("새로 온 직원분이 메뉴를 잘 몰라서 주문이 꼬였어요", "직원분이 중간에 바뀐 것 같았는데 괜찮았어요"),
    ("meat_low", "rush_buy"): ("고기 추가가 한참 걸렸어요", "고기 추가가 조금 늦게 나왔어요"),
    ("blogger", "comp"): ("옆 테이블이 촬영하느라 시끄러웠어요", "옆 테이블에서 사진을 많이 찍더라고요"),
    ("walkin_group", "turn_away"): ("단체 손님이 입구에서 한참 실랑이하고 가셨어요", "단체 손님은 못 들어오고 홀은 조용했어요"),
}
REVIEW_FLAG = {   # the sim's decision flag on a party (reason code) -> (bad line, mild line); wins over REVIEW_AFFECTED
    "meat_swapped": ("삼겹살 먹으러 갔는데 다 떨어져서 목살만 먹었어요", "삼겹살이 떨어져서 목살로 먹었는데 그것도 괜찮았어요"),
    "noisy_group": ("옆에 단체 손님이 너무 시끄러웠어요", "옆 단체 테이블이 좀 시끌벅적했어요"),
    "moved_inside": ("비 때문에 밖에서 먹다가 안으로 옮겨야 했어요", "비가 와서 안으로 자리를 옮겨 주셨어요"),
    "rain_tarp": ("천막 아래서 비 맞으며 먹었어요", "비 오는 날 천막 아래서 먹는 것도 나쁘지 않았어요"),
}
FLAG_KIND = {"meat_swapped": "meat_low", "noisy_group": "walkin_group", "moved_inside": "rain_burst", "rain_tarp": "rain_burst"}

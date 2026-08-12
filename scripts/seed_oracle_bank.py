"""生成银行交易系统模拟数据并写入 oracle-free 容器 (Oracle 26ai Free)。

用法:
    python scripts/seed_oracle_bank.py

可选环境变量:
    ORACLE_DSN          连接串，默认 localhost:1521/FREEPDB1
    ORACLE_SYSTEM_PWD   SYSTEM 密码，默认 YourPassword123
    BANK_USER           应用用户，默认 BANK
    BANK_PWD            应用用户密码，默认 Bank123456
    BANK_N_USERS        客户数，默认 2000
    BANK_N_TRANS        业务流水条数，默认 100000
"""
import os
import random
import sys
from datetime import date, datetime, timedelta

import oracledb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DSN = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
SYSTEM_PWD = os.environ.get("ORACLE_SYSTEM_PWD", "YourPassword123")
BANK_USER = os.environ.get("BANK_USER", "BANK").upper()
BANK_PWD = os.environ.get("BANK_PWD", "Bank123456")
N_USERS = int(os.environ.get("BANK_N_USERS", "2000"))
N_TRANS = int(os.environ.get("BANK_N_TRANS", "100000"))

RNG = random.Random(20260812)
ANCHOR = datetime(2026, 8, 12, 23, 59, 59)

AREA_CODES = [
    "110105", "310101", "310115", "440304", "440305", "330106",
    "320102", "510107", "610113", "120101", "500112", "440106",
]

SURNAMES = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田胡凌霍虞万支柯管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍卻璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公")

GIVEN_NAMES = list("伟芳娜敏静丽强磊军洋勇艳杰娟涛明超秀霞平刚桂英华玉萍红玲建华志强建军建国文华小平桂兰旭东雪梅海燕秀兰玉梅丽华丽娟桂芳春燕志明亚军玉兰海涛秀英晓燕丽丽晓明雪峰志刚晓华海峰建军永强晓东雪松志伟海燕丽娜晓芳雪梅丽君秀珍国华春梅玉珍海霞建军晓敏丽娟秀芳海涛志强")

CORP_SUFFIX = ["科技有限公司", "信息技术有限公司", "贸易有限公司", "实业有限公司", "供应链管理有限公司", "投资管理有限公司", "医疗器械有限公司", "建筑工程有限公司", "物流有限公司", "餐饮管理有限公司", "网络科技有限公司", "文化传媒有限公司"]
CORP_PREFIX = ["华信", "中科", "恒达", "金诚", "远航", "联创", "天翼", "宏图", "博远", "瑞丰", "鼎盛", "启明", "汇通", "新锐", "卓越"]

RISK_LEVELS = ["LOW"] * 55 + ["MEDIUM"] * 30 + ["HIGH"] * 15
USER_STATUS = ["ACTIVE"] * 98 + ["INACTIVE"] * 2
ACCOUNT_STATUS = ["ACTIVE"] * 97 + ["FROZEN"] * 2 + ["CLOSED"] * 1
TRANS_STATUS = ["SUCCESS"] * 985 + ["PENDING"] * 5 + ["FAIL"] * 10

REMARKS = ["客户要求加急处理", "大额交易复核通过", "风险交易人工审核", "节假日顺延到账", "渠道异常重试成功"]


# ---------------- 工具函数 ----------------
def luhn_digits(prefix: str) -> str:
    """根据前缀生成通过 Luhn 校验的卡号。"""
    digits = [int(c) for c in prefix]
    for _ in range(15 - len(prefix)):
        digits.append(RNG.randrange(0, 10))
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    check = (10 - total % 10) % 10
    return prefix + "".join(map(str, digits)) + str(check)


def gen_personal_id(birth: date, gender: str) -> str:
    area = RNG.choice(AREA_CODES)
    seq = RNG.randrange(0, 1000)
    if gender == "M":
        seq = seq | 1
    else:
        seq = seq & ~1
    base = area + birth.strftime("%Y%m%d") + f"{seq:03d}"
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check = "10X98765432"
    total = sum(int(c) * w for c, w in zip(base, weights))
    return base + check[total % 11]


def gen_uscc() -> str:
    return "91" + RNG.choice(AREA_CODES) + "".join(str(RNG.randrange(0, 10)) for _ in range(9))


def gen_phone() -> str:
    return "1" + RNG.choice("358") + "".join(str(RNG.randrange(0, 10)) for _ in range(9))


def gen_user_no(used: set) -> str:
    while True:
        no = "U" + f"{RNG.randrange(10**8):08d}"
        if no not in used:
            used.add(no)
            return no


def gen_account_no(used: set, kind: str) -> str:
    prefix = "62" if kind != "CORP" else "93"
    while True:
        no = luhn_digits(prefix)
        if no not in used:
            used.add(no)
            return no


def gen_serial_no(ts: datetime, used: set) -> str:
    while True:
        no = "TX" + ts.strftime("%Y%m%d") + f"{RNG.randrange(10**12):012d}"
        if no not in used:
            used.add(no)
            return no


def gen_external_acct(used: set) -> str:
    while True:
        no = luhn_digits(RNG.choice(["62", "88", "99"]))
        if no not in used:
            used.add(no)
            return no


# ---------------- 机构 ----------------
BRANCHES = ["上海分行", "北京分行", "深圳分行", "广州分行", "杭州分行", "成都分行"]
SUB_BRANCHES = ["浦东支行", "徐汇支行", "静安支行", "朝阳支行", "海淀支行", "西城支行",
                "福田支行", "南山支行", "罗湖支行", "天河支行", "越秀支行", "西湖支行",
                "拱墅支行", "高新支行", "武侯支行", "锦江支行", "雁塔支行", "碑林支行"]


def build_orgs() -> list:
    orgs = []
    region_by_id = {}
    orgs.append((1, "中国模拟银行总行", "HEAD", None, "HEAD_OFFICE", "北京", "ACTIVE"))
    region_by_id[1] = "北京"
    branch_ids = []
    for i, name in enumerate(BRANCHES, start=1):
        oid = 100 + i
        region = name[:2]
        orgs.append((oid, "中国模拟银行" + name, "BRANCH", 1, "BRANCH", region, "ACTIVE"))
        region_by_id[oid] = region
        branch_ids.append(oid)
    sub_ids = []
    for i, name in enumerate(SUB_BRANCHES, start=1):
        oid = 200 + i
        parent = branch_ids[(i - 1) % len(branch_ids)]
        region = region_by_id[parent]
        orgs.append((oid, "中国模拟银行" + name, "SUB_BRANCH", parent, "SUB_BRANCH", region, "ACTIVE"))
        region_by_id[oid] = region
        sub_ids.append(oid)
    for i in range(1, 31):
        oid = 300 + i
        parent = sub_ids[(i - 1) % len(sub_ids)]
        region = region_by_id[parent]
        orgs.append((oid, f"中国模拟银行{region}网点{i:02d}", "POINT", parent, "POINT", region, "ACTIVE"))
        region_by_id[oid] = region
    return orgs


# ---------------- 用户 ----------------
def build_users(orgs: list) -> list:
    point_ids = [o[0] for o in orgs if o[2] in ("POINT", "SUB_BRANCH")]
    branch_ids = [o[0] for o in orgs if o[2] in ("BRANCH", "SUB_BRANCH")]
    used_no, used_cert = set(), set()
    users = []
    n_personal = int(N_USERS * 0.9)
    for i in range(1, N_USERS + 1):
        created = datetime(
            RNG.randint(2015, 2025), RNG.randint(1, 12), RNG.randint(1, 28),
            RNG.randint(0, 23), RNG.randint(0, 59), RNG.randint(0, 59),
        )
        if i <= n_personal:
            gender = RNG.choice(["M", "F"])
            birth = date(RNG.randint(1960, 2005), RNG.randint(1, 12), RNG.randint(1, 28))
            cert_no = gen_personal_id(birth, gender)
            while cert_no in used_cert:
                birth = date(RNG.randint(1960, 2005), RNG.randint(1, 12), RNG.randint(1, 28))
                cert_no = gen_personal_id(birth, gender)
            used_cert.add(cert_no)
            name = RNG.choice(SURNAMES) + RNG.choice(GIVEN_NAMES)
            cert_type, user_type = "ID", "PERSONAL"
            org_id = RNG.choice(point_ids)
            email = f"user{i}@example.com"
        else:
            gender = None
            birth = None
            cert_no = gen_uscc()
            while cert_no in used_cert:
                cert_no = gen_uscc()
            used_cert.add(cert_no)
            name = RNG.choice(CORP_PREFIX) + RNG.choice(CORP_SUFFIX)
            cert_type, user_type = "USCC", "CORP"
            org_id = RNG.choice(branch_ids)
            email = f"contact{i}@{name[:6]}.com"
        users.append((
            i,
            gen_user_no(used_no),
            name,
            cert_type,
            cert_no,
            gender,
            birth,
            gen_phone(),
            email,
            f"{RNG.choice(['上海市', '北京市', '深圳市', '广州市', '杭州市', '成都市'])}{RNG.choice(['浦东新区', '朝阳区', '福田区', '天河区', '西湖区', '武侯区'])}{RNG.randint(1, 999)}号",
            RNG.choice(RISK_LEVELS),
            user_type,
            org_id,
            RNG.choice(USER_STATUS),
            created,
            created + timedelta(days=RNG.randint(0, 120)) if RNG.random() < 0.8 else None,
        ))
    return users


# ---------------- 账户 ----------------
def build_accounts(users: list, orgs: list) -> list:
    used_no = set()
    accounts = []
    aid = 1
    for u in users:
        _, _, name, _, _, gender, birth, phone, email, address, risk, user_type, org_id, status, created, updated = u
        if user_type == "PERSONAL":
            types = RNG.choices(
                ["SAVINGS", "CHECKING", "FINANCE"], weights=[55, 35, 10], k=1 + (1 if RNG.random() < 0.45 else 0)
            )
        else:
            types = ["CORP_BASIC"] + (["CORP_GEN"] if RNG.random() < 0.7 else [])
        for acct_type in types:
            if acct_type == "SAVINGS":
                balance = RNG.randint(0, 500000)
            elif acct_type == "CHECKING":
                balance = RNG.randint(0, 100000)
            elif acct_type == "FINANCE":
                balance = RNG.randint(10000, 2000000)
            elif acct_type == "CORP_BASIC":
                balance = RNG.randint(100000, 20000000)
            else:
                balance = RNG.randint(0, 5000000)
            balance = round(balance, 2)
            open_date = (created or datetime(2020, 1, 1)).date() + timedelta(days=RNG.randint(1, 60))
            accounts.append((
                aid,
                gen_account_no(used_no, acct_type),
                u[0],
                org_id,
                acct_type,
                "CNY",
                balance,
                round(balance * RNG.uniform(0.5, 1.0), 2),
                open_date,
                RNG.choice(ACCOUNT_STATUS),
            ))
            aid += 1
    return accounts


# ---------------- 交易配置 ----------------
# (code, name, channel, type, fee_rate, fee_min, fee_max, single_limit, daily_limit, weight, status)
CONFIGS = [
    ("DEP_CASH", "现金存款", "COUNTER", "DEPOSIT", 0, 0, 0, 500000, 1000000, 6, "ACTIVE"),
    ("WDR_CASH", "现金取款", "COUNTER", "WITHDRAW", 0, 0, 0, 200000, 500000, 6, "ACTIVE"),
    ("ATM_WDR", "ATM取款", "ATM", "WITHDRAW", 0.0005, 2, 50, 20000, 50000, 9, "ACTIVE"),
    ("TRF_INT", "行内转账", "ONLINE", "TRANSFER", 0, 0, 0, 500000, 2000000, 12, "ACTIVE"),
    ("TRF_CROSS", "跨行转账", "ONLINE", "TRANSFER", 0.0002, 1, 50, 500000, 2000000, 10, "ACTIVE"),
    ("TRF_OFFLINE", "柜面转账", "COUNTER", "TRANSFER", 0.0005, 2, 30, 1000000, 3000000, 4, "ACTIVE"),
    ("PAY_QR", "扫码支付", "MOBILE", "PAYMENT", 0.001, 0, 5, 50000, 200000, 15, "ACTIVE"),
    ("PAY_ONLINE", "网上支付", "INTERNET", "PAYMENT", 0.001, 0, 10, 100000, 500000, 12, "ACTIVE"),
    ("PAY_POS", "POS消费", "POS", "PAYMENT", 0.001, 0, 10, 100000, 300000, 8, "ACTIVE"),
    ("MOBILE_TOPUP", "手机充值", "MOBILE", "PAYMENT", 0, 0, 0, 1000, 5000, 5, "ACTIVE"),
    ("SALARY", "代发工资", "COUNTER", "DEPOSIT", 0, 0, 0, 0, 0, 4, "ACTIVE"),
    ("AUTO_UTILITY", "代扣水电费", "AUTO", "PAYMENT", 0.0005, 1, 10, 10000, 30000, 4, "ACTIVE"),
    ("ETC_DEBIT", "ETC扣款", "AUTO", "PAYMENT", 0.0005, 0, 5, 5000, 20000, 3, "ACTIVE"),
    ("FIN_BUY", "理财申购", "ONLINE", "FINANCE", 0.001, 5, 100, 5000000, 10000000, 3, "ACTIVE"),
    ("FIN_REDEEM", "理财赎回", "ONLINE", "FINANCE", 0, 0, 0, 5000000, 10000000, 2, "ACTIVE"),
    ("FUND_BUY", "基金申购", "ONLINE", "FINANCE", 0.0015, 5, 50, 2000000, 5000000, 2, "ACTIVE"),
    ("INS_SELL", "保险代销", "COUNTER", "FINANCE", 0.002, 10, 100, 1000000, 3000000, 1, "ACTIVE"),
    ("LOAN_ISSUE", "贷款放款", "COUNTER", "LOAN", 0, 0, 0, 5000000, 10000000, 1, "ACTIVE"),
    ("LOAN_REPAY", "贷款还款", "AUTO", "REPAY", 0, 0, 0, 500000, 2000000, 3, "ACTIVE"),
    ("CC_REPAY", "信用卡还款", "ONLINE", "REPAY", 0.001, 1, 20, 200000, 1000000, 4, "ACTIVE"),
    ("FX_BUY", "购汇结汇", "COUNTER", "FX", 0.002, 10, 200, 100000, 500000, 1, "ACTIVE"),
    ("DEP_FIXED", "定期存款", "COUNTER", "DEPOSIT", 0, 0, 0, 5000000, 10000000, 2, "ACTIVE"),
    ("TFR_FIXED2CUR", "定期转活期", "ONLINE", "DEPOSIT", 0, 0, 0, 5000000, 10000000, 1, "ACTIVE"),
    ("DEP_CORP", "对公存款", "COUNTER", "DEPOSIT", 0, 0, 0, 10000000, 50000000, 2, "ACTIVE"),
    ("LEGACY_TFR", "旧版柜面转账", "COUNTER", "TRANSFER", 0.0008, 3, 50, 500000, 1000000, 0, "INACTIVE"),
]


def sample_amount(trans_type: str) -> int:
    if trans_type == "DEPOSIT":
        return RNG.randint(100, 100000)
    if trans_type == "WITHDRAW":
        return RNG.randint(50, 50000)
    if trans_type == "TRANSFER":
        r = RNG.random()
        if r < 0.7:
            return RNG.randint(100, 50000)
        if r < 0.95:
            return RNG.randint(50000, 500000)
        return RNG.randint(500000, 2000000)
    if trans_type == "PAYMENT":
        return RNG.randint(1, 5000)
    if trans_type == "FINANCE":
        return RNG.randint(5000, 1000000)
    if trans_type == "LOAN":
        return RNG.randint(10000, 5000000)
    if trans_type == "REPAY":
        return RNG.randint(1000, 200000)
    return RNG.randint(500, 50000)


def calc_fee(cfg, amount: float) -> float:
    rate, fee_min, fee_max = cfg[4], cfg[5], cfg[6]
    if rate <= 0:
        return 0.0
    fee = amount * rate
    if fee_max > 0:
        fee = min(fee, fee_max)
    fee = max(fee, fee_min)
    return round(fee, 2)


def sample_time() -> datetime:
    r = RNG.random()
    if r < 0.55:
        days = RNG.randint(0, 90)
    elif r < 0.85:
        days = RNG.randint(91, 270)
    else:
        days = RNG.randint(271, 365)
    seconds = RNG.randint(0, 86399)
    return ANCHOR - timedelta(days=days, seconds=seconds)


def build_trans_logs(accounts: list, orgs: list, configs: list) -> list:
    account_nos = [a[1] for a in accounts]
    used_serial = set()
    used_external = set()
    log = []
    weights = [c[9] for c in configs]
    for _ in range(N_TRANS):
        cfg = RNG.choices(configs, weights=weights)[0]
        code, name, channel, trans_type = cfg[0], cfg[1], cfg[2], cfg[3]
        acct = RNG.choice(accounts)
        amount = float(sample_amount(trans_type))
        fee = calc_fee(cfg, amount)
        status = RNG.choice(TRANS_STATUS)
        ts = sample_time()
        serial = gen_serial_no(ts, used_serial)
        if trans_type in ("TRANSFER", "REPAY"):
            if RNG.random() < 0.8:
                counter = RNG.choice([n for n in account_nos if n != acct[1]])
            else:
                counter = gen_external_acct(used_external)
        elif trans_type == "PAYMENT":
            counter = gen_external_acct(used_external)
        elif trans_type in ("DEPOSIT", "FINANCE", "FX"):
            counter = None
        else:
            counter = gen_external_acct(used_external) if RNG.random() < 0.3 else None
        remark = RNG.choice(REMARKS) if RNG.random() < 0.02 else None
        log.append((
            serial, code, channel, trans_type, acct[1], counter,
            round(amount, 2), fee, status, ts, acct[3], acct[2], remark,
        ))
    return log


# ---------------- DDL ----------------
DDL = [
    """
    CREATE TABLE T_ORG (
        ORG_ID        NUMBER(10)    NOT NULL,
        ORG_NAME      VARCHAR2(100) NOT NULL,
        ORG_LEVEL     VARCHAR2(20)  NOT NULL,
        PARENT_ORG_ID NUMBER(10),
        ORG_TYPE      VARCHAR2(30)  NOT NULL,
        REGION        VARCHAR2(30),
        STATUS        VARCHAR2(10)  DEFAULT 'ACTIVE' NOT NULL,
        CREATED_AT    DATE          DEFAULT SYSDATE NOT NULL,
        CONSTRAINT PK_T_ORG PRIMARY KEY (ORG_ID),
        CONSTRAINT FK_T_ORG_PARENT FOREIGN KEY (PARENT_ORG_ID) REFERENCES T_ORG (ORG_ID)
    )""",
    """
    CREATE TABLE T_USER (
        USER_ID    NUMBER(12)   NOT NULL,
        USER_NO    VARCHAR2(20) NOT NULL,
        USER_NAME  VARCHAR2(100) NOT NULL,
        CERT_TYPE  VARCHAR2(10) NOT NULL,
        CERT_NO    VARCHAR2(32) NOT NULL,
        GENDER     VARCHAR2(2),
        BIRTH_DATE DATE,
        PHONE      VARCHAR2(20),
        EMAIL      VARCHAR2(64),
        ADDRESS    VARCHAR2(200),
        RISK_LEVEL VARCHAR2(10) DEFAULT 'LOW' NOT NULL,
        USER_TYPE  VARCHAR2(10) DEFAULT 'PERSONAL' NOT NULL,
        ORG_ID     NUMBER(10)   NOT NULL,
        STATUS     VARCHAR2(10) DEFAULT 'ACTIVE' NOT NULL,
        CREATED_AT DATE         DEFAULT SYSDATE NOT NULL,
        UPDATED_AT DATE,
        CONSTRAINT PK_T_USER PRIMARY KEY (USER_ID),
        CONSTRAINT UK_T_USER_NO UNIQUE (USER_NO),
        CONSTRAINT UK_T_USER_CERT UNIQUE (CERT_TYPE, CERT_NO),
        CONSTRAINT FK_T_USER_ORG FOREIGN KEY (ORG_ID) REFERENCES T_ORG (ORG_ID)
    )""",
    """
    CREATE TABLE T_ACCOUNT (
        ACCOUNT_ID        NUMBER(14)    NOT NULL,
        ACCOUNT_NO        VARCHAR2(32)  NOT NULL,
        USER_ID           NUMBER(12)    NOT NULL,
        ORG_ID            NUMBER(10)    NOT NULL,
        ACCOUNT_TYPE      VARCHAR2(20)  NOT NULL,
        CURRENCY          VARCHAR2(3)   DEFAULT 'CNY' NOT NULL,
        BALANCE           NUMBER(18,2)  DEFAULT 0 NOT NULL,
        AVAILABLE_BALANCE NUMBER(18,2)  DEFAULT 0 NOT NULL,
        OPEN_DATE         DATE          NOT NULL,
        STATUS            VARCHAR2(10)  DEFAULT 'ACTIVE' NOT NULL,
        CONSTRAINT PK_T_ACCOUNT PRIMARY KEY (ACCOUNT_ID),
        CONSTRAINT UK_T_ACCOUNT_NO UNIQUE (ACCOUNT_NO),
        CONSTRAINT FK_T_ACCOUNT_USER FOREIGN KEY (USER_ID) REFERENCES T_USER (USER_ID),
        CONSTRAINT FK_T_ACCOUNT_ORG FOREIGN KEY (ORG_ID) REFERENCES T_ORG (ORG_ID)
    )""",
    """
    CREATE TABLE T_TRANS_CONFIG (
        CONFIG_ID    NUMBER(10)    NOT NULL,
        TRANS_CODE   VARCHAR2(20)  NOT NULL,
        TRANS_NAME   VARCHAR2(100) NOT NULL,
        CHANNEL      VARCHAR2(20)  NOT NULL,
        TRANS_TYPE   VARCHAR2(20)  NOT NULL,
        FEE_RATE     NUMBER(10,6)  DEFAULT 0 NOT NULL,
        FEE_MIN      NUMBER(10,2)  DEFAULT 0 NOT NULL,
        FEE_MAX      NUMBER(10,2)  DEFAULT 0 NOT NULL,
        SINGLE_LIMIT NUMBER(18,2),
        DAILY_LIMIT  NUMBER(18,2),
        STATUS       VARCHAR2(10)  DEFAULT 'ACTIVE' NOT NULL,
        UPDATED_AT   DATE          DEFAULT SYSDATE NOT NULL,
        CONSTRAINT PK_T_TRANS_CONFIG PRIMARY KEY (CONFIG_ID),
        CONSTRAINT UK_T_TRANS_CONFIG_CODE UNIQUE (TRANS_CODE)
    )""",
    """
    CREATE TABLE T_TRANS_LOG (
        LOG_ID             NUMBER(16)    NOT NULL,
        TRANS_SERIAL_NO    VARCHAR2(40)  NOT NULL,
        TRANS_CODE         VARCHAR2(20)  NOT NULL,
        CHANNEL            VARCHAR2(20)  NOT NULL,
        TRANS_TYPE         VARCHAR2(20)  NOT NULL,
        ACCOUNT_NO         VARCHAR2(32)  NOT NULL,
        COUNTER_ACCOUNT_NO VARCHAR2(32),
        AMOUNT             NUMBER(18,2)  NOT NULL,
        FEE                NUMBER(10,2)  DEFAULT 0 NOT NULL,
        STATUS             VARCHAR2(10)  DEFAULT 'SUCCESS' NOT NULL,
        TRANS_TIME         DATE          NOT NULL,
        ORG_ID             NUMBER(10),
        USER_ID            NUMBER(12),
        REMARK             VARCHAR2(200),
        CONSTRAINT PK_T_TRANS_LOG PRIMARY KEY (LOG_ID),
        CONSTRAINT UK_T_TRANS_SERIAL UNIQUE (TRANS_SERIAL_NO),
        CONSTRAINT FK_T_LOG_ACCOUNT FOREIGN KEY (ACCOUNT_NO) REFERENCES T_ACCOUNT (ACCOUNT_NO),
        CONSTRAINT FK_T_LOG_ORG FOREIGN KEY (ORG_ID) REFERENCES T_ORG (ORG_ID),
        CONSTRAINT FK_T_LOG_USER FOREIGN KEY (USER_ID) REFERENCES T_USER (USER_ID)
    )""",
]

INDEXES = [
    "CREATE INDEX IDX_T_USER_ORG ON T_USER (ORG_ID)",
    "CREATE INDEX IDX_T_ACCOUNT_USER ON T_ACCOUNT (USER_ID)",
    "CREATE INDEX IDX_T_ACCOUNT_ORG ON T_ACCOUNT (ORG_ID)",
    "CREATE INDEX IDX_T_LOG_TIME ON T_TRANS_LOG (TRANS_TIME)",
    "CREATE INDEX IDX_T_LOG_ACCOUNT ON T_TRANS_LOG (ACCOUNT_NO)",
    "CREATE INDEX IDX_T_LOG_CODE ON T_TRANS_LOG (TRANS_CODE)",
    "CREATE INDEX IDX_T_LOG_ORG_TIME ON T_TRANS_LOG (ORG_ID, TRANS_TIME)",
]

TABLE_COMMENTS = {
    "T_ORG": "机构表：银行总行/分行/支行/网点组织架构",
    "T_USER": "用户表：个人客户与企业客户基础信息",
    "T_ACCOUNT": "账户表：客户在银行开立的账户及余额",
    "T_TRANS_CONFIG": "交易配置表：交易产品、渠道、费率与限额配置",
    "T_TRANS_LOG": "业务流水表：每笔交易的流水明细记录",
}

COLUMN_COMMENTS = {
    "T_ORG": {
        "ORG_ID": "机构号", "ORG_NAME": "机构名称", "ORG_LEVEL": "机构层级(HEAD/BRANCH/SUB_BRANCH/POINT)",
        "PARENT_ORG_ID": "上级机构号", "ORG_TYPE": "机构类型", "REGION": "所在地区",
        "STATUS": "状态(ACTIVE/INACTIVE)", "CREATED_AT": "创建时间",
    },
    "T_USER": {
        "USER_ID": "用户ID", "USER_NO": "客户编号", "USER_NAME": "客户名称",
        "CERT_TYPE": "证件类型(ID身份证/USCC统一社会信用代码)", "CERT_NO": "证件号码",
        "GENDER": "性别(M男/F女)", "BIRTH_DATE": "出生日期", "PHONE": "联系电话",
        "EMAIL": "电子邮箱", "ADDRESS": "联系地址", "RISK_LEVEL": "风险等级(LOW/MEDIUM/HIGH)",
        "USER_TYPE": "客户类型(PERSONAL个人/CORP企业)", "ORG_ID": "开户机构号",
        "STATUS": "状态(ACTIVE/INACTIVE)", "CREATED_AT": "建档时间", "UPDATED_AT": "更新时间",
    },
    "T_ACCOUNT": {
        "ACCOUNT_ID": "账户ID", "ACCOUNT_NO": "账号/卡号", "USER_ID": "所属用户ID",
        "ORG_ID": "开户机构号", "ACCOUNT_TYPE": "账户类型(SAVINGS/CHECKING/FINANCE/CORP_BASIC/CORP_GEN)",
        "CURRENCY": "币种", "BALANCE": "账户余额", "AVAILABLE_BALANCE": "可用余额",
        "OPEN_DATE": "开户日期", "STATUS": "状态(ACTIVE/FROZEN/CLOSED)",
    },
    "T_TRANS_CONFIG": {
        "CONFIG_ID": "配置ID", "TRANS_CODE": "交易码", "TRANS_NAME": "交易名称",
        "CHANNEL": "交易渠道(COUNTER/ATM/ONLINE/MOBILE/POS/AUTO/INTERNET)",
        "TRANS_TYPE": "交易类型(DEPOSIT/WITHDRAW/TRANSFER/PAYMENT/FINANCE/LOAN/REPAY/FX)",
        "FEE_RATE": "费率", "FEE_MIN": "最低手续费", "FEE_MAX": "最高手续费",
        "SINGLE_LIMIT": "单笔限额", "DAILY_LIMIT": "日累计限额",
        "STATUS": "状态(ACTIVE/INACTIVE)", "UPDATED_AT": "更新时间",
    },
    "T_TRANS_LOG": {
        "LOG_ID": "流水ID", "TRANS_SERIAL_NO": "交易流水号", "TRANS_CODE": "交易码",
        "CHANNEL": "交易渠道", "TRANS_TYPE": "交易类型", "ACCOUNT_NO": "本方账号",
        "COUNTER_ACCOUNT_NO": "对方账号", "AMOUNT": "交易金额", "FEE": "手续费",
        "STATUS": "交易状态(SUCCESS/PENDING/FAIL)", "TRANS_TIME": "交易时间",
        "ORG_ID": "交易机构号", "USER_ID": "用户ID", "REMARK": "备注",
    },
}

INSERT_CONFIG = (
    "INSERT INTO T_TRANS_CONFIG (CONFIG_ID, TRANS_CODE, TRANS_NAME, CHANNEL, TRANS_TYPE, FEE_RATE, FEE_MIN, "
    "FEE_MAX, SINGLE_LIMIT, DAILY_LIMIT, STATUS) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11)"
)

INSERT_LOG = (
    "INSERT INTO T_TRANS_LOG (LOG_ID, TRANS_SERIAL_NO, TRANS_CODE, CHANNEL, TRANS_TYPE, ACCOUNT_NO, "
    "COUNTER_ACCOUNT_NO, AMOUNT, FEE, STATUS, TRANS_TIME, ORG_ID, USER_ID, REMARK) "
    "VALUES (SEQ_T_TRANS_LOG.NEXTVAL, :1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13)"
)


# ---------------- 执行 ----------------
def drop_table(cur, name: str) -> None:
    cur.execute(f"""
        BEGIN
            EXECUTE IMMEDIATE 'DROP TABLE {name} CASCADE CONSTRAINTS';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE != -942 THEN RAISE; END IF;
        END;""")


def setup_schema(conn) -> None:
    cur = conn.cursor()
    for t in ("T_TRANS_LOG", "T_TRANS_CONFIG", "T_ACCOUNT", "T_USER", "T_ORG"):
        drop_table(cur, t)
    cur.execute("BEGIN EXECUTE IMMEDIATE 'DROP SEQUENCE SEQ_T_TRANS_LOG'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -2289 THEN RAISE; END IF; END;")
    for ddl in DDL:
        cur.execute(ddl)
    for idx in INDEXES:
        cur.execute(idx)
    cur.execute("CREATE SEQUENCE SEQ_T_TRANS_LOG START WITH 1 INCREMENT BY 1 NOCACHE")
    for table, comment in TABLE_COMMENTS.items():
        esc = comment.replace(chr(39), chr(39) * 2)
        cur.execute('COMMENT ON TABLE ' + table + ' IS ' + chr(39) + esc + chr(39))
        for col, c in COLUMN_COMMENTS[table].items():
            esc_c = c.replace(chr(39), chr(39) * 2)
            cur.execute('COMMENT ON COLUMN ' + table + '.' + col + ' IS ' + chr(39) + esc_c + chr(39))
    conn.commit()


def ensure_bank_user(sys_conn) -> None:
    cur = sys_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dba_users WHERE username = :1", [BANK_USER])
    if cur.fetchone()[0] == 0:
        cur.execute(f'CREATE USER {BANK_USER} IDENTIFIED BY "{BANK_PWD}"')
        cur.execute(f"GRANT CONNECT, RESOURCE TO {BANK_USER}")
        cur.execute(f"ALTER USER {BANK_USER} DEFAULT TABLESPACE USERS")
        cur.execute(f"ALTER USER {BANK_USER} QUOTA UNLIMITED ON USERS")
        sys_conn.commit()
        print(f"[OK] 已创建应用用户 {BANK_USER}")
    else:
        print(f"[OK] 应用用户 {BANK_USER} 已存在，跳过创建")


def insert_rows(conn, sql: str, rows: list, batch: int = 2000) -> None:
    cur = conn.cursor()
    total = len(rows)
    for start in range(0, total, batch):
        cur.executemany(sql, rows[start:start + batch])
        conn.commit()
    print(f"[OK] 插入 {total} 行")


def verify(conn) -> None:
    cur = conn.cursor()
    print("\n===== 数据校验 =====")
    for t in ("T_ORG", "T_USER", "T_ACCOUNT", "T_TRANS_CONFIG", "T_TRANS_LOG"):
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t}: {cur.fetchone()[0]} 行")
    cur.execute("SELECT COUNT(*), ROUND(SUM(AMOUNT), 2), ROUND(AVG(AMOUNT), 2) FROM T_TRANS_LOG WHERE STATUS='SUCCESS'")
    cnt, total, avg = cur.fetchone()
    print(f"  成功流水: {cnt} 笔, 总金额: {total:,.2f}, 平均: {avg:,.2f}")
    cur.execute("""
        SELECT c.TRANS_NAME, COUNT(*), ROUND(SUM(l.AMOUNT), 2)
        FROM T_TRANS_LOG l JOIN T_TRANS_CONFIG c ON c.TRANS_CODE = l.TRANS_CODE
        GROUP BY c.TRANS_NAME ORDER BY COUNT(*) DESC FETCH FIRST 5 ROWS ONLY""")
    print("  交易类型 Top5:")
    for name, cnt, amt in cur.fetchall():
        print(f"    {name}: {cnt} 笔, 金额 {amt:,.2f}")
    cur.execute("""
        SELECT l.TRANS_SERIAL_NO, u.USER_NAME, a.ACCOUNT_NO, c.TRANS_NAME, l.AMOUNT, l.STATUS, l.TRANS_TIME
        FROM T_TRANS_LOG l
        JOIN T_USER u ON u.USER_ID = l.USER_ID
        JOIN T_ACCOUNT a ON a.ACCOUNT_NO = l.ACCOUNT_NO
        JOIN T_TRANS_CONFIG c ON c.TRANS_CODE = l.TRANS_CODE
        ORDER BY l.TRANS_TIME DESC FETCH FIRST 5 ROWS ONLY""")
    print("  最新流水样例:")
    for row in cur.fetchall():
        print("   ", row)


def main() -> None:
    print(f"连接: {DSN} (SYSTEM 创建应用用户) ...")
    sys_conn = oracledb.connect(user="SYSTEM", password=SYSTEM_PWD, dsn=DSN)
    ensure_bank_user(sys_conn)
    sys_conn.close()

    print(f"以 {BANK_USER} 连接并初始化表结构 ...")
    conn = oracledb.connect(user=BANK_USER, password=BANK_PWD, dsn=DSN)
    setup_schema(conn)

    print("生成机构数据 ...")
    orgs = build_orgs()
    insert_rows(conn, "INSERT INTO T_ORG (ORG_ID, ORG_NAME, ORG_LEVEL, PARENT_ORG_ID, ORG_TYPE, REGION, STATUS) VALUES (:1, :2, :3, :4, :5, :6, :7)", orgs)

    print("生成用户数据 ...")
    users = build_users(orgs)
    insert_rows(conn, (
        "INSERT INTO T_USER (USER_ID, USER_NO, USER_NAME, CERT_TYPE, CERT_NO, GENDER, BIRTH_DATE, PHONE, EMAIL, "
        "ADDRESS, RISK_LEVEL, USER_TYPE, ORG_ID, STATUS, CREATED_AT, UPDATED_AT) "
        "VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13, :14, :15, :16)"
    ), users)

    print("生成账户数据 ...")
    accounts = build_accounts(users, orgs)
    insert_rows(conn, (
        "INSERT INTO T_ACCOUNT (ACCOUNT_ID, ACCOUNT_NO, USER_ID, ORG_ID, ACCOUNT_TYPE, CURRENCY, BALANCE, "
        "AVAILABLE_BALANCE, OPEN_DATE, STATUS) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10)"
    ), accounts)

    print("生成交易配置数据 ...")
    config_rows = [(i + 1, c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8], c[10]) for i, c in enumerate(CONFIGS)]
    insert_rows(conn, INSERT_CONFIG, config_rows)

    print(f"生成业务流水数据（{N_TRANS} 条） ...")
    logs = build_trans_logs(accounts, orgs, CONFIGS)
    insert_rows(conn, INSERT_LOG, logs, batch=2000)

    verify(conn)
    conn.close()
    print("\n完成！")


if __name__ == "__main__":
    main()

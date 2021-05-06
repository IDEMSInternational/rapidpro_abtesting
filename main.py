import json

from abtest import ABTest
from rapidpro_abtest_creator import RapidProABTestCreator


def main():
    test1_rows = [
        ["replace_bit_of_text","ABTesting_Pre",1,"The first personalizable message.","message.","message, Steve!",True],
        ["replace_bit_of_text","ABTesting_Pre",3,"Good morning!","Good morning!","Good morning, Steve!",False],
    ]
    test2_rows = [
        ["replace_bit_of_text","ABTesting_Pre",3,"Good morning!","Good morning","g00d m0rn1ng",False],
    ]
    abtest1 = ABTest("Personalization", test1_rows)
    abtest2 = ABTest("Some1337Text", test2_rows)
    abtests = [abtest1, abtest2]

    filename = "testdata/Linear_OneNodePerAction.json"
    rpx = RapidProABTestCreator(filename)
    rpx.apply_abtests(abtests)
    rpx.export_to_json("out.json")


if __name__ == '__main__':
    main()

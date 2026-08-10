"""Offline unit checks for Harmony xpath (no device)."""
from kea2.hmXpath import xpath_first, HMXpathElement


def _tree():
    return {
        "attributes": {"type": "root", "bounds": "[0,0][100,200]"},
        "children": [
            {
                "attributes": {
                    "type": "Text",
                    "text": "首页",
                    "description": "home_tab",
                    "bounds": "[10,20][80,60]",
                },
                "children": [],
            },
            {
                "attributes": {
                    "type": "Button",
                    "text": "",
                    "description": "搜索",
                    "bounds": "[90,20][140,60]",
                },
                "children": [],
            },
        ],
    }


def test_xpath_text_and_description():
    h = _tree()
    b, a = xpath_first(h, "//*[@text='首页']")
    assert b == [10, 20, 80, 60]
    assert a.get("text") == "首页"
    b2, a2 = xpath_first(h, "//*[@description='搜索']")
    assert b2 == [90, 20, 140, 60]
    assert a2.get("description") == "搜索"


def test_xpath_element_static_lock():
    class Fake:
        _static_locked = True
        _hierarchy = _tree()

        def dump_hierarchy(self):
            raise AssertionError("should not dump when static")

        def _hierarchy_fingerprint(self):
            return (1, ())

        def _click_xy(self, x, y):
            self.xy = (x, y)
            return True

        def _bust_live(self):
            pass

        def _settle_after_action(self, **kw):
            pass

    d = Fake()
    el = HMXpathElement(d, "//*[@text='首页']")
    assert el.exists()
    el.click()
    assert d.xy == (45, 40)
    assert not HMXpathElement(d, "//*[@text='不存在']").exists()


if __name__ == "__main__":
    test_xpath_text_and_description()
    test_xpath_element_static_lock()
    print("ok")

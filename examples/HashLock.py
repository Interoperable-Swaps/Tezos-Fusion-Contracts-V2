# HashLock Example.

import smartpy as sp

@sp.module
def main():
    class HashLock(sp.Contract):
        def __init__(self, hash):
            self.data.hash = hash

        @sp.entrypoint
        def check(self,param):
            sp.cast(
                param,
                sp.record(secret=sp.bytes, value=sp.nat).layout(
                    ("secret", "value")
                ),
            )
            hash = sp.keccak(param.secret)

            assert hash == self.data.hash, "Invalid Secret"
            # self.data.storedValue = hash

if "main" in __name__:

    @sp.add_test()
    def test():
        scenario = sp.test_scenario("HashLock Example")

        secret = sp.bytes("0xa13c7be0e8f1b5b9926dc25f13c31476598e3e6012592f4e82633eb0be87a028")
        secret_hash = sp.keccak(secret)

        c1 = main.HashLock(secret_hash)
        scenario.h1("HashLock Example")
        scenario += c1

        scenario.h2("Entering Invalid Secret")
        password = sp.pack("A StrinAg")
        c1.check(secret = password, value = 100, _valid=False)

        scenario.h2("Entering Valid Secret")
        c1.check(secret = secret, value = 100)

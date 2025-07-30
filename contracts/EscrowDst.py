# Destination Escrow.
import smartpy as sp

@sp.module
def main():
    class DestinationEscrow(sp.Contract):

        def __init__(self, orderHash: sp.bytes, hash: sp.bytes,
            maker: sp.address, taker: sp.address,
            tokenAddress :sp.address, tokenId : sp.nat, tokenType : sp.bool,
            amount: sp.nat, safetyDeposit : sp.mutez,
            DstWithdrawal: sp.nat, DstPublicWithdrawal: sp.nat, DstCancellation: sp.nat
            ):

            # Add Rescue Delay Function
            # TokenHolder Access for public withdraw
            # sp.cast(
            #     init_params,
            #     sp.record(orderHash=sp.bytes, hash=sp.bytes, maker=sp.address, taker=sp.address,
            #         tokenAddress = sp.address, tokenId = sp.nat, tokenType = sp.bool,
            #         amount=sp.nat, safetyDeposit = sp.mutez).layout(
            #         ("secret", "value")
            #     ),
            # )

            self.data.orderHash = orderHash
            self.data.hash = hash
            self.data.maker = maker
            self.data.taker = taker
            self.data.tokenAddress = tokenAddress
            self.data.tokenId = tokenId
            self.data.tokenType = tokenType
            self.data.amount = amount
            self.data.safetyDeposit = safetyDeposit

            self.data.startTime = sp.now
            self.data.DstWithdrawal = DstWithdrawal
            self.data.DstPublicWithdrawal = DstPublicWithdrawal
            self.data.DstCancellation = DstCancellation


        # Private Functions for Checking
        @sp.private(with_storage="read-only")
        def onlyTaker(self, sender):
            return sender == self.data.taker

        @sp.private(with_storage="read-only")
        def onlyBefore(self, addTime):
            return sp.add_seconds(self.data.startTime, sp.to_int(addTime)) > sp.now

        @sp.private(with_storage="read-only")
        def onlyAfter(self, addTime):
            return sp.now > sp.add_seconds(self.data.startTime, sp.to_int(addTime))

        @sp.private(with_storage="read-only")
        def onlyValidSecret(self, secret):
            return self.data.hash == sp.keccak(secret)

        # Functions
        # withdraw
        # cancel
        # rescue Funds
        # publicWithdraw

        # ---- contract deployed --/-- finality --/-- PRIVATE WITHDRAWAL --/-- PUBLIC WITHDRAWAL --/-- private cancellation ----
        @sp.entry_point
        def withdraw(self, secret):
            sp.cast(secret, sp.bytes)

            assert self.onlyTaker(sp.sender), "INVALID_TAKER"

            assert self.onlyAfter(self.data.DstWithdrawal), "AFTER_WITHDRAWL"

            assert self.onlyBefore(self.data.DstCancellation), "BEFORE_CANCELLATION"

            assert self.onlyValidSecret(secret), "INVALID_SECRET"

            # Transfer Tokens to the Maker
            # Transfer native tokens to the Taker

        # ---- contract deployed --/-- finality --/-- private withdrawal --/-- PUBLIC WITHDRAWAL --/-- private cancellation ----
        @sp.entry_point
        def publicWithdraw(self, secret):
            sp.cast(secret, sp.bytes)

            assert self.onlyAfter(self.data.DstPublicWithdrawal), "AFTER_WITHDRAWL"

            assert self.onlyBefore(self.data.DstCancellation), "BEFORE_CANCELLATION"

            assert self.onlyValidSecret(secret), "INVALID_SECRET"

             # Transfer Tokens to the Maker
             # Transfer native tokens to the Taker

        # ---- contract deployed --/-- finality --/-- private withdrawal --/-- public withdrawal --/-- PRIVATE CANCELLATION ----
        @sp.entry_point
        def cancel(self):

            assert self.onlyTaker(sp.sender), "INVALID_TAKER"

            assert self.onlyAfter(self.data.DstCancellation), "AFTER_CANCEL"

             # Transfer Tokens to the Taker
             # Transfer native tokens to the Taker



if "main" in __name__:

    @sp.add_test()
    def test():
        scenario = sp.test_scenario("Destination Escrow")

         # sp.test_account generates ED25519 key-pairs deterministically:
        Maker = sp.test_account("Maker")
        Resolver = sp.test_account("Resolver")
        Bob = sp.test_account("Bob")
        Token = sp.test_account("Token")

        orderHash = sp.pack("OrderId-1")
        secret = sp.bytes("0xa13c7be0e8f1b5b9926dc25f13c31476598e3e6012592f4e82633eb0be87a028")
        secret_hash = sp.keccak(secret)

        destinationEscrow = main.DestinationEscrow(
            orderHash,
            secret_hash,
            Maker.address,
            Resolver.address,
            Token.address,
            0,
            False,
            100,
            sp.tez(10),
            10,
            20,
            20
        )
        scenario.h1("Destination Escrow")
        scenario += destinationEscrow

        # scenario.h2("Entering Invalid Secret")
        # password = sp.pack("A StrinAg")
        # c1.check(secret = password, value = 100, _valid=False)

        # scenario.h2("Entering Valid Secret")
        # c1.check(secret = secret, value = 100)

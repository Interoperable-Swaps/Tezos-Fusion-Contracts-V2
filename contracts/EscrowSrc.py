# Source Escrow.
import smartpy as sp

@sp.module
def t():
    tx: type = sp.record(
        to_=sp.address,
        token_id=sp.nat,
        amount=sp.nat,
    ).layout(("to_", ("token_id", "amount")))

    transfer_batch: type = sp.record(
        from_=sp.address,
        txs=list[tx],
    ).layout(("from_", "txs"))

    transfer_params: type = list[transfer_batch]


@sp.module
def main():

    import t

    class EscrowSrc(sp.Contract):

        def __init__(self, orderHash: sp.bytes, hash: sp.bytes,
            maker: sp.address, taker: sp.address,
            token :sp.address, tokenId : sp.nat, tokenType : sp.bool,
            amount: sp.nat, safetyDeposit : sp.mutez,
            SrcWithdrawal: sp.nat, SrcPublicWithdrawal: sp.nat, SrcCancellation: sp.nat, SrcPublicCancellation: sp.nat
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
            self.data.token = token
            self.data.tokenId = tokenId
            self.data.tokenType = tokenType
            self.data.amount = amount
            self.data.safetyDeposit = safetyDeposit
            # TimeLocks Data
            self.data.startTime = sp.now
            self.data.SrcWithdrawal = SrcWithdrawal
            self.data.SrcPublicWithdrawal = SrcPublicWithdrawal
            self.data.SrcCancellation = SrcCancellation
            self.data.SrcPublicCancellation = SrcPublicCancellation


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

        @sp.private(with_operations=True,with_storage="read-only")
        def TransferTokens(self, receiver):
            if self.data.tokenType:
                transferHandle = sp.contract(
                    t.transfer_params,
                    self.data.token,
                    "transfer"
                )

                TransferParam = [
                            sp.record(
                                from_ = sp.self_address,
                                txs = [
                                    sp.record(
                                        to_         = receiver,
                                        token_id    = self.data.tokenId,
                                        amount      = self.data.amount
                                    )
                                ]
                            )
                        ]

                match transferHandle:
                    case Some(contract):
                        sp.transfer(TransferParam, sp.mutez(0), contract)
                    case None:
                        sp.trace("Failed to find contract")

            else:
                TransferParam = sp.record(
                    from_ = sp.self_address,
                    to_ = receiver,
                    value = self.data.amount
                )

                transferHandle = sp.contract(
                    sp.record(from_=sp.address, to_=sp.address, value=sp.nat).layout(
                    ("from_ as from", ("to_ as to", "value"))
                    ),
                    self.data.token,
                    "transfer"
                    )

                match transferHandle:
                    case Some(contract):
                        sp.transfer(TransferParam, sp.mutez(0), contract)
                    case None:
                        sp.trace("Failed to find contract")


        # Functions
        # withdraw
        # cancel
        # rescue Funds
        # publicWithdraw

        # ---- contract deployed --/-- finality --/-- PRIVATE WITHDRAWAL --/-- PUBLIC WITHDRAWAL --/--
        #  * --/-- private cancellation --/-- public cancellation ----
        @sp.entry_point
        def withdraw(self, secret):
            sp.cast(secret, sp.bytes)

            assert self.onlyTaker(sp.sender), "INVALID_TAKER"

            assert self.onlyAfter(self.data.SrcWithdrawal), "AFTER_WITHDRAWL"

            assert self.onlyBefore(self.data.SrcCancellation), "BEFORE_CANCELLATION"

            assert self.onlyValidSecret(secret), "INVALID_SECRET"

            # Transfer Tokens to the Taker
            self.TransferTokens(self.data.taker)
            # Transfer native tokens to the Taker
            sp.send(self.data.taker, self.data.safetyDeposit)


         # ---- contract deployed --/-- finality --/-- PRIVATE WITHDRAWAL --/-- PUBLIC WITHDRAWAL --/--
         #  * --/-- private cancellation --/-- public cancellation ----
        @sp.entry_point
        def withdrawTo(self, param):
            sp.cast(
                param,
                sp.record(secret=sp.bytes, target=sp.address).layout(
                    ("secret", "target")
                ),
            )

            assert self.onlyTaker(sp.sender), "INVALID_TAKER"

            assert self.onlyAfter(self.data.SrcWithdrawal), "AFTER_WITHDRAWL"

            assert self.onlyBefore(self.data.SrcCancellation), "BEFORE_CANCELLATION"

            assert self.onlyValidSecret(param.secret), "INVALID_SECRET"

            # Transfer Tokens to the Taker
            self.TransferTokens(param.target)
            # Transfer native tokens to the Target
            sp.send(self.data.taker, self.data.safetyDeposit)

        # ---- contract deployed --/-- finality --/-- private withdrawal --/-- PUBLIC WITHDRAWAL --/-- private cancellation ----
        @sp.entry_point
        def publicWithdraw(self, secret):
            sp.cast(secret, sp.bytes)

            assert self.onlyAfter(self.data.SrcPublicWithdrawal), "AFTER_WITHDRAWL"

            assert self.onlyBefore(self.data.SrcCancellation), "BEFORE_CANCELLATION"

            assert self.onlyValidSecret(secret), "INVALID_SECRET"

            # Transfer Tokens to the Taker
            self.TransferTokens(self.data.taker)
            # Transfer native tokens to the Sender
            sp.send(sp.sender, self.data.safetyDeposit)

        # ---- contract deployed --/-- finality --/-- private withdrawal --/-- public withdrawal --/-- PRIVATE CANCELLATION ----/-- PUBLIC CANCELLATION ----
        @sp.entry_point
        def cancel(self):

            assert self.onlyTaker(sp.sender), "INVALID_TAKER"

            assert self.onlyAfter(self.data.SrcCancellation), "AFTER_CANCEL"

            # Transfer Tokens to the Maker
            self.TransferTokens(self.data.maker)
            # Transfer native tokens to the Taker
            sp.send(sp.sender, self.data.safetyDeposit)

        #---- contract deployed --/-- finality --/-- private withdrawal --/-- public withdrawal --/--
        # * --/-- private cancellation --/-- PUBLIC CANCELLATION ---
        @sp.entry_point
        def publicCancel(self):

            assert self.onlyAfter(self.data.SrcPublicCancellation), "AFTER_PUBLIC_CANCEL"

            # Transfer Tokens to the Maker
            self.TransferTokens(self.data.maker)
            # Transfer native tokens to the Taker
            sp.send(sp.sender, self.data.safetyDeposit)

if "main" in __name__:

    @sp.add_test()
    def test():
        scenario = sp.test_scenario("Source Escrow")

         # sp.test_account generates ED25519 key-pairs deterministically:
        Maker = sp.test_account("Maker")
        Resolver = sp.test_account("Resolver")
        Bob = sp.test_account("Bob")
        Token = sp.test_account("Token")

        orderHash = sp.pack("OrderId-1")
        secret = sp.bytes("0xa13c7be0e8f1b5b9926dc25f13c31476598e3e6012592f4e82633eb0be87a028")
        secret_hash = sp.keccak(secret)

        SourceEscrow = main.EscrowSrc(
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
            20,
            25
        )
        scenario.h1("Source Escrow")
        scenario += SourceEscrow

        # scenario.h2("Entering Invalid Secret")
        # password = sp.pack("A StrinAg")
        # c1.withdraw(secret = password, _valid=False)

        # scenario.h2("Entering Valid Secret")
        # c1.check(secret = secret, value = 100)

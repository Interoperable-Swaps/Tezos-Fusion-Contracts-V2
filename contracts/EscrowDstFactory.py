from importlib.metadata import entry_points
# Destination Escrow Factory.
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

    EscrowDstStorage: type = sp.record(DstCancellation = sp.nat, DstPublicWithdrawal = sp.nat, DstWithdrawal = sp.nat,
        amount = sp.nat, hash = sp.bytes, maker = sp.address, orderHash = sp.bytes, safetyDeposit = sp.mutez,
        taker = sp.address, token = sp.address, tokenId = sp.nat, tokenType = sp.bool, startTime = sp.timestamp
    )

    EscrowInitParams: type = sp.record(DstCancellation = sp.nat, DstPublicWithdrawal = sp.nat, DstWithdrawal = sp.nat,
        amount = sp.nat, hash = sp.bytes, maker = sp.address, orderHash = sp.bytes, safetyDeposit = sp.mutez,
        taker = sp.address, token = sp.address, tokenId = sp.nat, tokenType = sp.bool)


    EscrowCallParams: type = sp.record(DstCancellation = sp.nat, DstPublicWithdrawal = sp.nat, DstWithdrawal = sp.nat, srcCancellationTimestamp = sp.timestamp,
        amount = sp.nat, hash = sp.bytes, maker = sp.address, orderHash = sp.bytes, safetyDeposit = sp.mutez,
        taker = sp.address, token = sp.address, tokenId = sp.nat, tokenType = sp.bool)

    class EscrowDst(sp.Contract):

        def __init__(self, init_params):

            # Add Rescue Delay Function
            # TokenHolder Access for public withdraw
            sp.cast(self.data, EscrowDstStorage)

            sp.cast(init_params, EscrowInitParams)

            self.data.orderHash = init_params.orderHash
            self.data.hash = init_params.hash
            self.data.maker = init_params.maker
            self.data.taker = init_params.taker
            self.data.token = init_params.token
            self.data.tokenId = init_params.tokenId
            self.data.tokenType = init_params.tokenType
            self.data.amount = init_params.amount
            self.data.safetyDeposit = init_params.safetyDeposit
            # TimeLocks Data
            self.data.startTime = sp.now
            self.data.DstWithdrawal = init_params.DstWithdrawal
            self.data.DstPublicWithdrawal = init_params.DstPublicWithdrawal
            self.data.DstCancellation = init_params.DstCancellation


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
        # TODO: rescue Funds
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
            self.TransferTokens(self.data.maker)

            # Transfer native tokens to the Taker
            sp.send(self.data.taker, self.data.safetyDeposit)


        # ---- contract deployed --/-- finality --/-- private withdrawal --/-- PUBLIC WITHDRAWAL --/-- private cancellation ----
        @sp.entry_point
        def publicWithdraw(self, secret):
            sp.cast(secret, sp.bytes)

            assert self.onlyAfter(self.data.DstPublicWithdrawal), "AFTER_WITHDRAWL"

            assert self.onlyBefore(self.data.DstCancellation), "BEFORE_CANCELLATION"

            assert self.onlyValidSecret(secret), "INVALID_SECRET"

            # Transfer Tokens to the Maker
            self.TransferTokens(self.data.maker)
            # Transfer native tokens to the sp.sender
            sp.send(sp.sender, self.data.safetyDeposit)

        # ---- contract deployed --/-- finality --/-- private withdrawal --/-- public withdrawal --/-- PRIVATE CANCELLATION ----
        @sp.entry_point
        def cancel(self):

            assert self.onlyTaker(sp.sender), "INVALID_TAKER"

            assert self.onlyAfter(self.data.DstCancellation), "AFTER_CANCEL"

            # Transfer Tokens to the Taker
            self.TransferTokens(self.data.maker)
            # Transfer native tokens to the Taker
            sp.send(self.data.taker, self.data.safetyDeposit)


    class EscrowDstFactory(sp.Contract):

        def __init__(self, init_params):

            # Add Rescue Delay Function
            # TokenHolder Access for public withdraw
            sp.cast(
                init_params,
                sp.record(admin = sp.address, LOP = sp.address)
            )

            self.data.admin = init_params.admin
            self.data.LOP = init_params.LOP

        @sp.private()
        def CheckTimeStamps(self, DstCancellation, DstPublicWithdrawal, DstWithdrawal):

            if DstCancellation > DstPublicWithdrawal:
                if DstPublicWithdrawal > DstWithdrawal:
                    return True
                else:
                    return False
            else:
                return False

        @sp.private(with_operations=True)
        def TransferTokens(self, sender, receiver, amount, tokenAddress,id, faTwoFlag):

            if faTwoFlag:
                transferHandle = sp.contract(
                    t.transfer_params,
                    tokenAddress,
                    "transfer"
                )

                TransferParam = [
                            sp.record(
                                from_ = sender,
                                txs = [
                                    sp.record(
                                        to_         = receiver,
                                        token_id    = id,
                                        amount      = amount
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
                    from_ = sender,
                    to_ = receiver,
                    value = amount
                )

                transferHandle = sp.contract(
                    sp.record(from_=sp.address, to_=sp.address, value=sp.nat).layout(
                    ("from_ as from", ("to_ as to", "value"))
                    ),
                    tokenAddress,
                    "transfer"
                    )

                match transferHandle:
                    case Some(contract):
                        sp.transfer(TransferParam, sp.mutez(0), contract)
                    case None:
                        sp.trace("Failed to find contract")

        @sp.entry_point
        def changeAdmin(self, newAdmin):

            sp.cast(newAdmin, sp.address)

            assert sp.sender == self.data.admin

            self.data.admin = newAdmin


        @sp.entry_point
        def deployEscrowDst(self, params):

            sp.cast(
                params,
                EscrowCallParams
            )

            assert sp.sender == self.data.LOP, "NOT_LOP"

            assert sp.amount == params.safetyDeposit, "INVALID_AMOUNT"

            assert params.safetyDeposit > sp.tez(1), "SMALL_AMOUNT"

            assert self.CheckTimeStamps((sp.record(DstCancellation = params.DstCancellation, DstPublicWithdrawal = params.DstPublicWithdrawal, DstWithdrawal = params.DstWithdrawal))), "INVALID_TIMESTAMP"

            assert sp.add_seconds(sp.now, sp.to_int(params.DstCancellation)) > params.srcCancellationTimestamp, "DIFF"

            self.TransferTokens(sp.record(
                sender = params.taker, receiver = sp.self_address, amount = params.amount , tokenAddress = params.token,id = params.tokenId, faTwoFlag = params.tokenType
            ))

            newContract = sp.create_contract(
                EscrowDst,
                None,
                sp.amount,
                sp.record(
                    DstCancellation = params.DstCancellation, DstPublicWithdrawal = params.DstPublicWithdrawal, DstWithdrawal = params.DstWithdrawal,
                    amount = params.amount, hash = params.hash, maker = params.maker, orderHash = params.orderHash, safetyDeposit = params.safetyDeposit,
                    taker = params.taker, token = params.token, tokenId = params.tokenId, tokenType = params.tokenType, startTime = sp.now
                )
            )

            self.TransferTokens(sp.record(
                sender = sp.self_address, receiver = newContract, amount = params.amount , tokenAddress = params.token,id = params.tokenId, faTwoFlag = params.tokenType
            ))

            sp.emit(sp.record(newEscrow=newContract, orderHash = params.orderHash, hashLock=params.hash), tag="deployedDstEscrow", with_type=True)


if "main" in __name__:

    @sp.add_test()
    def test():
        scenario = sp.test_scenario("Destination Escrow Factory")

        # sp.test_account generates ED25519 key-pairs deterministically:
        Maker = sp.test_account("Maker")
        Resolver = sp.test_account("Resolver")
        Bob = sp.test_account("Bob")
        Token = sp.test_account("Token")

        orderHash = sp.pack("OrderId-1")
        secret = sp.bytes("0xa13c7be0e8f1b5b9926dc25f13c31476598e3e6012592f4e82633eb0be87a028")
        secret_hash = sp.keccak(secret)

        scenario.h1("Destination Escrow Factory")

        destinationEscrowFactory = main.EscrowDstFactory(sp.record(admin = Bob.address))
        scenario += destinationEscrowFactory

        destinationEscrowFactory.deployEscrowDst(sp.record(DstCancellation = 20, DstPublicWithdrawal = 15, DstWithdrawal = 10, srcCancellationTimestamp = sp.timestamp(2),
            amount = 100, hash = secret_hash, maker = Maker.address, orderHash = orderHash, safetyDeposit = sp.tez(10),
            taker = Resolver.address,
            token = Token.address, tokenId = 0, tokenType = False), _sender = Bob, _now = sp.timestamp(100), _amount = sp.tez(10))


        # destinationEscrow = main.EscrowDst(
        #     sp.record(DstCancellation = 20, DstPublicWithdrawal = 15, DstWithdrawal = 10,
        #     amount = 100, hash = secret_hash, maker = Maker.address, orderHash = orderHash, safetyDeposit = sp.tez(1),
        #     taker = Resolver.address,
        #     token = Token.address, tokenId = 0, tokenType = False)
        # )
        # scenario.h1("Destination Escrow")
        # scenario += destinationEscrow

        # scenario.h2("Entering Invalid Secret")
        # password = sp.pack("A StrinAg")
        # c1.check(secret = password, value = 100, _valid=False)

        # scenario.h2("Entering Valid Secret")
        # c1.check(secret = secret, value = 100)

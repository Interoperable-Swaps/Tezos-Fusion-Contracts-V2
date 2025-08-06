from importlib.metadata import entry_points
# Limit Order Protocol.
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

    EscrowSrcCallParams: type = sp.record(
        salt = sp.nat, receiver = sp.bytes, makerAsset = sp.address,takerAsset = sp.bytes, makingAmount = sp.nat, takingAmount = sp.nat,
        makerSignature = sp.signature, makerKey = sp.key,
        SrcCancellation = sp.nat, SrcPublicCancellation = sp.nat, SrcPublicWithdrawal = sp.nat, SrcWithdrawal = sp.nat,
        amount = sp.nat, hash = sp.bytes, maker = sp.address, orderHash = sp.bytes,
        safetyDeposit = sp.mutez, taker = sp.address, token = sp.address, tokenId = sp.nat, tokenType = sp.bool)

    EscrowDstCallParams: type = sp.record(DstCancellation = sp.nat, DstPublicWithdrawal = sp.nat, DstWithdrawal = sp.nat, srcCancellationTimestamp = sp.timestamp,
        amount = sp.nat, hash = sp.bytes, maker = sp.address, orderHash = sp.bytes, safetyDeposit = sp.mutez,
        taker = sp.address, token = sp.address, tokenId = sp.nat, tokenType = sp.bool)

    class LimitOrderProtocol(sp.Contract):

        def __init__(self, init_params):

            sp.cast(
                init_params,
                sp.record(admin = sp.address, escrowSrcFactory = sp.address, escrowDstFactory = sp.address)
            )

            self.data.admin = init_params.admin
            self.data.escrowSrcFactory = init_params.escrowSrcFactory
            self.data.escrowDstFactory = init_params.escrowDstFactory

        @sp.entry_point
        def changeAdmin(self, newAdmin):

            sp.cast(newAdmin, sp.address)

            assert sp.sender == self.data.admin

            self.data.admin = newAdmin


        @sp.entry_point
        def changeEscrowSrcFactory(self, newEscrowSrcFactory):

            sp.cast(newEscrowSrcFactory, sp.address)

            assert sp.sender == self.data.admin

            self.data.escrowSrcFactory = newEscrowSrcFactory


        @sp.entry_point
        def changeEscrowDstFactory(self, newEscrowDstFactory):

            sp.cast(newEscrowDstFactory, sp.address)

            assert sp.sender == self.data.admin

            self.data.escrowDstFactory = newEscrowDstFactory

        @sp.entry_point
        def deployEscrowDst(self, params):

            sp.cast(params, EscrowDstCallParams)


        @sp.entry_point
        def deployEscrowSrc(self, params):

            sp.cast(params, EscrowSrcCallParams)

            signData = sp.pack(sp.record(
                salt = sp.nat, receiver = sp.bytes, makerAsset = sp.address,takerAsset = sp.bytes, makingAmount = sp.nat, takingAmount = sp.nat
            ))

            assert sp.check_signature(self.data.makerKey, params.makerSignature, signData)

            # Call Escrow Src Factory


if "main" in __name__:

    @sp.add_test()
    def test():
        scenario = sp.test_scenario("Limit Order Contract")

        # sp.test_account generates ED25519 key-pairs deterministically:
        Maker = sp.test_account("Maker")
        Resolver = sp.test_account("Resolver")
        Bob = sp.test_account("Bob")
        Token = sp.test_account("Token")

        orderHash = sp.pack("OrderId-1")
        secret = sp.bytes("0xa13c7be0e8f1b5b9926dc25f13c31476598e3e6012592f4e82633eb0be87a028")
        secret_hash = sp.keccak(secret)

        LOP = main.LimitOrderProtocol(sp.record(admin = Bob.address,
            escrowSrcFactory = Maker.address, escrowDstFactory = Maker.address))
        scenario += LOP

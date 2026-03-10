import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../core/AuthContext';
import { apiClient } from '../core/apiClient';

export default function TransactionDetail() {
  const { id } = useParams<{ id: string }>();
  const { tenant } = useAuth();
  const navigate = useNavigate();
  
  const [txn, setTxn] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isIssuing, setIsIssuing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchTxn = async () => {
      if (!tenant || !id) return;
      
      setIsLoading(true);
      try {
        const response = await apiClient.get(`/v1/tenants/${tenant.id}/transactions/${id}`);
        setTxn(response.data.data);
      } catch (err: any) {
        setError(err.response?.data?.error?.message || 'Failed to fetch detail');
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchTxn();
  }, [tenant, id]);

  const handleIssueReceipt = async () => {
    if (!tenant || !id) return;
    setIsIssuing(true);
    setError('');
    
    try {
      const idempotencyKey = Date.now().toString();
      await apiClient.post(
        `/v1/tenants/${tenant.id}/transactions/${id}/issue-document`,
        {},
        { headers: { 'Idempotency-Key': idempotencyKey } }
      );
      
      // Optimistic update
      setTxn((prev: any) => ({ ...prev, receiptState: 'pending' }));
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Failed to issue receipt');
    } finally {
      setIsIssuing(false);
    }
  };

  if (isLoading) return <div className="p-8">Loading...</div>;
  if (error && !txn) return <div className="p-8 text-red-600">Error: {error}</div>;
  if (!txn) return <div className="p-8">Transaction not found</div>;

  const isCompleted = txn.status === 'completed';
  const canIssue = isCompleted && txn.receiptState === 'none';

  return (
    <div className="px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => navigate('/transactions')}
          className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
        >
          &larr; Back
        </button>
        <h1 className="text-2xl font-bold leading-6 text-gray-900">Transaction Details</h1>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 p-4 rounded-md">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      <div className="overflow-hidden bg-white shadow sm:rounded-lg mb-8">
        <div className="px-4 py-6 sm:px-6 flex justify-between items-center bg-gray-50 border-b border-gray-200">
          <div>
            <h3 className="text-3xl font-semibold leading-7 text-gray-900">
              {(txn.amount / 100).toFixed(2)} {txn.currency}
            </h3>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-gray-500">
              {txn.id}
            </p>
          </div>
          <div>
            <span className={`inline-flex items-center rounded-md px-3 py-1 text-sm font-medium ring-1 ring-inset ${
              isCompleted 
                ? 'bg-green-50 text-green-700 ring-green-600/20'
                : 'bg-yellow-50 text-yellow-800 ring-yellow-600/20'
            }`}>
              {txn.status.toUpperCase()}
            </span>
          </div>
        </div>
        
        <div className="border-t border-gray-100">
          <dl className="divide-y divide-gray-100">
            <div className="px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
              <dt className="text-sm font-medium text-gray-900">Date created</dt>
              <dd className="mt-1 text-sm leading-6 text-gray-700 sm:col-span-2 sm:mt-0">
                {new Date(txn.createdAt).toLocaleString()}
              </dd>
            </div>
            <div className="px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6 bg-gray-50">
              <dt className="text-sm font-medium text-gray-900">Customer</dt>
              <dd className="mt-1 text-sm leading-6 text-gray-700 sm:col-span-2 sm:mt-0">
                {txn.customerEmail || txn.customerPhone || 'N/A'}
              </dd>
            </div>
            <div className="px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
              <dt className="text-sm font-medium text-gray-900">Provider Source</dt>
              <dd className="mt-1 text-sm leading-6 text-gray-700 sm:col-span-2 sm:mt-0">
                {txn.providerType}
              </dd>
            </div>
            <div className="px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6 bg-gray-50">
              <dt className="text-sm font-medium text-gray-900">Provider TXN ID</dt>
              <dd className="mt-1 text-sm leading-6 text-gray-700 sm:col-span-2 sm:mt-0 font-mono">
                {txn.providerTransactionId}
              </dd>
            </div>
            <div className="px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6 items-center">
              <dt className="text-sm font-medium text-gray-900">Receipt State</dt>
              <dd className="mt-1 text-sm leading-6 text-gray-700 sm:col-span-2 sm:mt-0 flex items-center justify-between">
                <span className="font-semibold">{txn.receiptState.toUpperCase()}</span>
                
                {canIssue && (
                  <button
                    onClick={handleIssueReceipt}
                    disabled={isIssuing}
                    className="rounded-md bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-50"
                  >
                    {isIssuing ? 'Issuing...' : 'Issue Receipt'}
                  </button>
                )}
                
                {txn.receiptState === 'pending' && (
                  <span className="text-orange-600 text-sm italic">Working...</span>
                )}
                
                {txn.receiptState === 'issued' && (
                  <button
                    className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                  >
                    Download PDF
                  </button>
                )}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}

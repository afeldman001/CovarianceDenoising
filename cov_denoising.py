"""
Adapted from Marcos M. Lòpez de Prado, "Machine Learning for Asset Managers" (2020), Section 2 
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.neighbors import KernelDensity

def mpPDF(var, q, pts):
    """Marcenko-Pastur probability density function 
       q = T/N"""
    eMin, eMax = var*(1-(1./q)**0.5)**2, var*(1+(1./q)**0.5)**2
    eVal = np.linspace(eMin, eMax, pts)
    pdf = q/(2*np.pi*var*eVal) * np.sqrt((eMax-eVal)*(eVal-eMin))
    # Ensure one-dimensional data for Series creation
    pdf = pd.Series(pdf.flatten(), index=eVal.flatten())
    return pdf

def getPCA(matrix):
    """Perform PCA (eigen decomposition) on a symmetric matrix and return sorted eigenvalues and eigenvectors."""
    eVal, eVec = np.linalg.eigh(matrix)  # Compute eigenvalues and eigenvectors
    indices = eVal.argsort()[::-1]  # Sort eigenvalues in descending order
    eVal, eVec = eVal[indices], eVec[:, indices]  # Reorder eigenvectors accordingly
    eVal = np.diagflat(eVal)  # Convert eigenvalues to a diagonal matrix
    return eVal, eVec


def fitKDE(obs, bWidth=0.01, x=None, kernel='gaussian'):
    """ Fits a kernel density estimator (KDE) to the given observations. """
    if len (obs.shape) == 1:obs=obs.reshape(-1, 1)
    kde = KernelDensity(kernel=kernel, bandwidth=bWidth).fit(obs)
    if x is None: 
        x=np.unique(obs).reshape(-1, 1)
    if len(x.shape) == 1:x=x.reshape(-1, 1)
    logProb=kde.score_samples(x) # log(density)
    pdf = pd.Series(np.exp(logProb), index = x.flatten())
    return pdf

def getCovMatrix(returns):
    """
    Compute the empirical covariance matrix from stock returns using the dot-product method.

    Parameters:
    -----------
    returns : pd.DataFrame
        DataFrame where each column represents the returns of a stock.

    Returns:
    --------
    np.ndarray
        Covariance matrix of the stock returns.
    """
    X = returns.values  # Convert DataFrame to NumPy array
    X -= X.mean(axis=0)  # Demean returns
    T = X.shape[0]  # Number of time periods
    cov = np.dot(X.T, X) / (T - 1)  # Compute covariance matrix
    return cov

def cov2corr(cov):
    """ derive the correlation matrix from a covariance matrix """
    std = np.sqrt(np.diag(cov))
    corr = cov / np.outer(std, std)
    corr[corr < -1], corr[corr > 1] = -1, 1 # numerical error
    return corr

def errPDFs(var, eVal, q, bWidth, pts=1000):
    """
    Calculate error between theoretical and empirical PDFs.
    
    Parameters:
    -----------
    var : float
        Variance parameter for MP distribution
    eVal : array-like
        Empirical eigenvalues
    q : float
        Ratio of observations to variables
    bWidth : float
        Bandwidth for kernel density estimation
    pts : int, default=1000
        Number of points for PDF evaluation
    
    Returns:
    --------
    float
        Sum of squared errors between PDFs
    """
    # Calculate theoretical MP distribution
    pdf0 = mpPDF(var, q, pts)
    
    # Fit empirical distribution using KDE
    pdf1 = fitKDE(eVal, bWidth=bWidth, x=pdf0.index.values)
    
    # Calculate sum of squared errors
    sse = np.sum((pdf1 - pdf0)**2)
    
    return sse

def findMaxEval(eVal, q, bWidth):
    """Find maximum eigenvalue threshold through MP distribution fitting"""
    out = minimize(lambda *x: errPDFs(*x), 0.5,
                  args=(eVal, q, bWidth),
                  bounds=((1e-5, 1-1e-5),))
    if out ['success']: var=out['x'][0]
    else: var = 1
    eMax = var*(1+(1./q)**0.5)**2
    return eMax, var

def denoisedCorr(eVal, eVec, nFacts):
    # remove noise from corr by fixing random eigenvalues
    eVal_ = np.diag(eVal).copy()
    eVal_[nFacts:] = eVal_[nFacts:].sum() / float(eVal_.shape[0] - nFacts)
    eVal_ = np.diag(eVal_)
    corr1 = np.dot(eVec, eVal_).dot(eVec.T)
    corr1 = cov2corr(corr1)
    return corr1

def denoisedCorr2(eVal, eVec, nFacts, alpha = 0):
    # remove noise from corr through targeted shrinkage 
    eValL, eVecL = eVal[:nFacts, :nFacts], eVec[:, :nFacts]
    eValR, eVecR = eVal[nFacts:, nFacts:], eVec[:, nFacts:]
    corr0 = np.dot(eVecL, eValL).dot(eVecL.T)
    corr1 = np.dot(eVecR, eValR).dot(eVecR.T)
    corr2 = corr0 + alpha * corr1 + (1 - alpha) * np.diag(np.diag(corr1))
    return corr2